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
    ) -> None:
        self.gemini_client = gemini_client
        self.store_name = store_name

    def can_handle(self, request: ChatRequest) -> bool:
        if not self.store_name:
            return False
        sources = [source.strip() for source in (request.sources or []) if source.strip()]
        if not sources:
            return True
        return all(source == self.store_name for source in sources)

    async def handle(self, request: ChatRequest, *, history: Optional[List[str]] = None) -> ChatResponse:
        metadata_filters: List[MetadataFilter] = []
        filter_summaries: List[str] = []
        enhanced_query = request.query

        if request.common_product:
            metadata_filters.append(MetadataFilter(key="product", value=request.common_product, operator="EQUALS"))
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

        payload = {
            "text": result["text"],
            "groundingChunks": result.get("grounding_chunks", []),
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
            metadata_filters.append(MetadataFilter(key="product", value=request.common_product, operator="EQUALS"))
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
    return CommonChatHandler(gemini_client=client, store_name=store_name)
