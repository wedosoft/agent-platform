from __future__ import annotations

import asyncio
import logging
import os
import threading
from typing import List, Optional

from fastapi import HTTPException, status

from app.core.config import get_settings
from app.models.metadata import MetadataFilter
from app.models.session import ChatRequest, ChatResponse
from app.services.gemini_client import GeminiClientError
from app.services.gemini_file_search_client import GeminiFileSearchClient
from app.services.common_documents import CommonDocumentsService, get_common_documents_service

LOGGER = logging.getLogger(__name__)

SYSTEM_INSTRUCTION = (
    "You are a helpful customer support assistant. "
    "Answer the user's question based ONLY on the provided search results (Context). "
    "If the answer is not in the context, politely state that you cannot find the information."
)


class CommonChatHandler:
    def __init__(
        self,
        *,
        gemini_client: GeminiFileSearchClient,
        store_name: str,
        documents_service: Optional[CommonDocumentsService] = None,
    ) -> None:
        self.gemini_client = gemini_client
        self.store_name = store_name
        self.documents_service = documents_service

    def can_handle(self, request: ChatRequest) -> bool:
        if not self.store_name:
            return False
        sources = [source.strip() for source in (request.sources or []) if source.strip()]
        if not sources:
            return True
        return all(source == self.store_name for source in sources)

    def _enrich_chunks_with_metadata(self, chunks: List[dict]) -> List[dict]:
        if not self.documents_service or not chunks:
            return chunks

        slug_map = {}
        slugs_to_fetch = set()

        for chunk in chunks:
            retrieved = chunk.get("retrievedContext") or {}
            title = retrieved.get("title")
            if not title:
                continue
            
            # Try to extract slug from title (format: {slug}-{lang})
            # We try stripping known suffixes
            slug = None
            for lang in ["ko", "en"]:
                suffix = f"-{lang}"
                if title.endswith(suffix):
                    slug = title[:-len(suffix)]
                    break
            
            if slug:
                slugs_to_fetch.add(slug)
                # Map title to slug for later lookup
                slug_map[title] = slug

        if not slugs_to_fetch:
            return chunks

        try:
            docs = self.documents_service.fetch_by_slugs(list(slugs_to_fetch), columns=["slug", "full_path", "title_ko", "title_en"])
            doc_map = {doc["slug"]: doc for doc in docs}
            
            for chunk in chunks:
                retrieved = chunk.get("retrievedContext") or {}
                title = retrieved.get("title")
                if not title:
                    continue
                
                slug = slug_map.get(title)
                if slug and slug in doc_map:
                    doc = doc_map[slug]
                    # Inject metadata
                    retrieved["uri"] = doc.get("full_path")
                    # Optionally update title if needed, but keeping original is fine
                    # retrieved["title"] = doc.get("title_ko") or doc.get("title_en") or title
        except Exception as e:
            LOGGER.warning("Failed to enrich chunks with metadata: %s", e)

        return chunks

    async def handle(self, request: ChatRequest, *, history: Optional[List[str]] = None) -> ChatResponse:
        metadata_filters: List[MetadataFilter] = []
        filter_summaries: List[str] = []
        enhanced_query = request.query

        if request.common_product:
            # 메타데이터 필터: 제품명은 시스템 고정 값이므로 그대로 사용
            metadata_filters.append(MetadataFilter(key="product", value=request.common_product.strip(), operator="EQUALS"))

            filter_summaries.append(f"제품={request.common_product}")
            enhanced_query = f"[{request.common_product}] {request.query}"

        try:
            result = await self.gemini_client.search(
                query=enhanced_query,
                store_names=[self.store_name],
                metadata_filters=metadata_filters,
                conversation_history=history,
                system_instruction=SYSTEM_INSTRUCTION,
            )
        except GeminiClientError as exc:
            LOGGER.exception("Gemini 검색 실패")
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc

        grounding_chunks = result.get("grounding_chunks", [])
        grounding_chunks = self._enrich_chunks_with_metadata(grounding_chunks)

        payload = {
            "text": result["text"],
            "groundingChunks": grounding_chunks,
            "ragStoreName": self.store_name,
            "sources": [self.store_name],
            "filters": filter_summaries,
            "knownContext": {},
        }
        return ChatResponse.model_validate(payload)

    async def stream_handle(self, request: ChatRequest, *, history: Optional[List[str]] = None):
        metadata_filters: List[MetadataFilter] = []
        filter_summaries: List[str] = []
        enhanced_query = request.query

        if request.common_product:
            # 메타데이터 필터: 제품명은 시스템 고정 값이므로 그대로 사용
            metadata_filters.append(MetadataFilter(key="product", value=request.common_product.strip(), operator="EQUALS"))

            filter_summaries.append(f"제품={request.common_product}")
            enhanced_query = f"[{request.common_product}] {request.query}"

        try:
            async for event in self.gemini_client.stream_search(
                query=enhanced_query,
                store_names=[self.store_name],
                metadata_filters=metadata_filters,
                conversation_history=history,
                system_instruction=SYSTEM_INSTRUCTION,
            ):
                if event["event"] == "result":
                    payload = event["data"]
                    
                    grounding_chunks = payload.get("groundingChunks", [])
                    if grounding_chunks:
                        payload["groundingChunks"] = self._enrich_chunks_with_metadata(grounding_chunks)

                    payload.update(
                        {
                            "ragStoreName": self.store_name,
                            "sources": [self.store_name],
                            "filters": filter_summaries,
                            "knownContext": {},
                        }
                    )
                    yield {"event": "result", "data": payload}
                else:
                    yield event
        except GeminiClientError as exc:
            yield {
                "event": "error",
                "data": {"message": str(exc) or "잠시 후 다시 시도해 주세요."},
            }



def get_common_chat_handler() -> Optional[CommonChatHandler]:
    settings = get_settings()
    api_key = settings.gemini_api_key or os.getenv("GEMINI_API_KEY")
    store_name = settings.gemini_common_store_name
    if not api_key or not store_name:
        return None
    client = GeminiFileSearchClient(
        api_key=api_key,
        primary_model=settings.gemini_primary_model,
        fallback_model=settings.gemini_fallback_model,
    )
    documents_service = get_common_documents_service()
    return CommonChatHandler(
        gemini_client=client, 
        store_name=store_name,
        documents_service=documents_service
    )
