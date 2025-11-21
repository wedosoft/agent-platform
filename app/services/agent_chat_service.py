from __future__ import annotations

from dataclasses import asdict
from typing import List, Optional, Tuple

from fastapi import HTTPException, status

from app.models.analyzer import AnalyzerResult
from app.models.metadata import MetadataFilter
from app.models.session import ChatRequest
from app.models.tenant import TenantConfig
from app.services.freshdesk_search_service import FreshdeskSearchResult, FreshdeskSearchService, get_freshdesk_search_service
from app.services.gemini_file_search_client import GeminiClientError, GeminiFileSearchClient
from app.services.query_filter_analyzer import QueryFilterAnalyzer, get_query_filter_analyzer


class AgentChatService:
    def __init__(
        self,
        *,
        gemini_client: GeminiFileSearchClient,
        analyzer: QueryFilterAnalyzer,
        freshdesk_search: Optional[FreshdeskSearchService] = None,
    ) -> None:
        self.gemini_client = gemini_client
        self.analyzer = analyzer
        self.freshdesk_search = freshdesk_search

    async def chat(
        self,
        *,
        tenant: TenantConfig,
        request: ChatRequest,
        history: List[str],
        clarification_state: Optional[dict] = None,
    ) -> Tuple[dict, AnalyzerResult]:
        analyzer_result = await self.analyzer.analyze(
            request.query,
            clarification_option=request.clarification_option,
            clarification_state=clarification_state,
        )
        metadata_filters = self._build_metadata_filters(
            tenant=tenant,
            request=request,
            analyzer_filters=analyzer_result.filters,
        )
        filter_summaries = self._build_filter_summaries(
            tenant=tenant,
            request=request,
            analyzer_summaries=analyzer_result.summaries,
        )
        freshdesk_result: Optional[FreshdeskSearchResult] = None

        if self.freshdesk_search and tenant.pipeline_type == "freshdesk_rag":
            freshdesk_result = await self.freshdesk_search.search_with_filters(analyzer_result)
            if freshdesk_result.ticket_ids:
                ticket_filter = MetadataFilter(
                    key="sourceId",
                    operator="IN",
                    value=",".join(str(ticket_id) for ticket_id in freshdesk_result.ticket_ids[:20]),
                )
                metadata_filters.append(ticket_filter)
                filter_summaries.append(f"티켓ID={len(freshdesk_result.ticket_ids)}개")

        store_names = self._resolve_store_names(tenant, request)
        if not store_names:
            raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Gemini store가 설정되어 있지 않습니다")

        try:
            gemini_payload = await self.gemini_client.search(
                query=request.query,
                store_names=store_names,
                metadata_filters=metadata_filters,
                conversation_history=history,
            )
        except GeminiClientError as exc:
            raise HTTPException(status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc

        payload = {
            "text": gemini_payload.get("text", "결과를 생성하지 못했습니다."),
            "groundingChunks": gemini_payload.get("grounding_chunks", []),
            "ragStoreName": tenant.gemini.default_store or store_names[0],
            "sources": store_names,
            "filters": filter_summaries,
            "filterConfidence": analyzer_result.confidence,
            "clarificationNeeded": analyzer_result.clarification_needed,
            "clarification": asdict(analyzer_result.clarification) if analyzer_result.clarification else None,
            "knownContext": analyzer_result.known_context,
        }

        if freshdesk_result:
            payload["freshdeskTickets"] = freshdesk_result.tickets
            payload["freshdeskSearchPlan"] = {
                "query": freshdesk_result.query_string,
                "plan": freshdesk_result.plan,
            }

        return payload, analyzer_result

    def _build_metadata_filters(
        self,
        *,
        tenant: TenantConfig,
        request: ChatRequest,
        analyzer_filters: List[MetadataFilter],
    ) -> List[MetadataFilter]:
        filters = list(tenant.build_metadata_filters())
        if request.common_product:
            # 동일 키(product) 중복을 방지하고 사용자가 선택한 제품으로 강제 고정
            filters = [f for f in filters if f.key != "product"]
            filters.insert(
                0,
                MetadataFilter(
                    key="product",
                    operator="EQUALS",
                    value=request.common_product,
                ),
            )
        filters.extend(analyzer_filters)
        return filters

    def _build_filter_summaries(
        self,
        *,
        tenant: TenantConfig,
        request: ChatRequest,
        analyzer_summaries: List[str],
    ) -> List[str]:
        product_label = request.common_product or tenant.product
        summaries = [f"제품={product_label}"] if product_label else []
        summaries.extend(analyzer_summaries)
        return summaries

    def _resolve_store_names(self, tenant: TenantConfig, request: ChatRequest) -> List[str]:
        if request.sources:
            return request.sources
        if tenant.gemini.store_names:
            return tenant.gemini.store_names
        return []


def get_agent_chat_service() -> AgentChatService:
    analyzer = get_query_filter_analyzer()
    if not analyzer or not analyzer.llm_client:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Gemini 필터 분석기가 구성되지 않았습니다")

    from app.core.config import get_settings

    settings = get_settings()
    api_key = settings.gemini_api_key
    if not api_key:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Gemini API key가 필요합니다")

    client = GeminiFileSearchClient(
        api_key=api_key,
        primary_model=settings.gemini_primary_model,
        fallback_model=settings.gemini_fallback_model,
    )
    freshdesk_service = get_freshdesk_search_service()
    return AgentChatService(
        gemini_client=client,
        analyzer=analyzer,
        freshdesk_search=freshdesk_service,
    )
