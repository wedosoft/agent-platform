from __future__ import annotations

import logging
import os
from typing import List, Optional

from fastapi import HTTPException, status

from app.core.config import get_settings
from app.models.metadata import MetadataFilter
from app.models.session import ChatRequest, ChatResponse
from app.services.gemini_client import GeminiClientError
from app.services.gemini_file_search_client import GeminiFileSearchClient

LOGGER = logging.getLogger(__name__)


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

    def handle(self, request: ChatRequest, *, history: Optional[List[str]] = None) -> ChatResponse:
        metadata_filters: List[MetadataFilter] = []
        filter_summaries: List[str] = []
        if request.common_product:
            metadata_filters.append(MetadataFilter(key="product", value=request.common_product, operator="EQUALS"))
            filter_summaries.append(f"제품={request.common_product}")

        try:
            result = self.gemini_client.search(
                query=request.query,
                store_names=[self.store_name],
                metadata_filters=metadata_filters,
                conversation_history=history,
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
