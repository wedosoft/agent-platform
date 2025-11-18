from __future__ import annotations

from dataclasses import asdict
from typing import List, Optional

from functools import lru_cache

from fastapi import HTTPException, status

from app.core.config import get_settings
from app.models.analyzer import AnalyzerResult
from app.models.session import ChatRequest
from app.services.gemini_client import GeminiClient, GeminiClientError
from app.services.query_filter_analyzer import QueryFilterAnalyzer, get_query_filter_analyzer


class TicketChatHandler:
    def __init__(
        self,
        *,
        gemini_client: GeminiClient,
        analyzer: QueryFilterAnalyzer,
        ticket_store_names: List[str],
    ) -> None:
        self.gemini_client = gemini_client
        self.analyzer = analyzer
        self.ticket_store_names = ticket_store_names

    def can_handle(self, request: ChatRequest) -> bool:
        if not self.ticket_store_names or not self.analyzer.llm_client:
            return False
        sources = request.sources or []
        if not sources:
            return False
        return all(source in self.ticket_store_names for source in sources)

    def handle(
        self,
        request: ChatRequest,
        *,
        history: List[str],
    ) -> tuple[dict, AnalyzerResult]:
        analyzer_result = self.analyzer.analyze(request.query)
        store_names = request.sources or self.ticket_store_names
        try:
            gemini_response = self.gemini_client.search(
                query=request.query,
                store_names=store_names,
                metadata_filters=analyzer_result.filters,
                conversation_history=history,
            )
        except GeminiClientError as exc:
            raise HTTPException(status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc

        payload = {
            "text": gemini_response.get("text", "검색 결과를 가져오지 못했습니다."),
            "groundingChunks": gemini_response.get("grounding_chunks", []),
            "ragStoreName": store_names[0] if store_names else None,
            "sources": gemini_response.get("store_names", store_names),
            "filters": analyzer_result.summaries,
            "filterConfidence": analyzer_result.confidence,
            "clarificationNeeded": analyzer_result.clarification_needed,
            "clarification": asdict(analyzer_result.clarification) if analyzer_result.clarification else None,
        }
        return payload, analyzer_result


@lru_cache
def get_ticket_chat_handler() -> Optional[TicketChatHandler]:
    settings = get_settings()
    analyzer = get_query_filter_analyzer()
    if not analyzer or not analyzer.llm_client:
        return None
    store_names = settings.gemini_ticket_store_names
    if not store_names:
        return None
    if not settings.gemini_api_key:
        return None
    client = GeminiClient(
        api_key=settings.gemini_api_key,
        primary_model=settings.gemini_primary_model,
        fallback_model=settings.gemini_fallback_model,
    )
    return TicketChatHandler(
        gemini_client=client,
        analyzer=analyzer,
        ticket_store_names=store_names,
    )