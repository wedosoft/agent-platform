from __future__ import annotations

import asyncio
import json
import os
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple

from functools import lru_cache

from app.core.config import get_settings
from app.models.analyzer import AnalyzerClarification, AnalyzerResult
from app.models.metadata import MetadataFilter
from app.services.freshdesk_metadata import FreshdeskMetadataService
from app.services.gemini_client import GeminiClient


class QueryFilterAnalyzer:
    """LLM 기반 필터 추출 + 안전한 fallback."""

    def __init__(
        self,
        *,
        fallback_months: int = 12,
        metadata_fields: Optional[List[str]] = None,
        metadata_service: Optional[FreshdeskMetadataService] = None,
    ) -> None:
        self.fallback_months = fallback_months
        self.allowed_fields = metadata_fields or ["priority", "status", "createdAt", "updatedAt"]
        self.metadata_service = metadata_service or FreshdeskMetadataService()
        settings = get_settings()
        api_key = settings.gemini_api_key or os.getenv("GEMINI_API_KEY")
        self.llm_client: GeminiClient | None = None
        if api_key:
            self.llm_client = GeminiClient(
                api_key=api_key,
                primary_model=settings.gemini_primary_model,
                fallback_model=settings.gemini_fallback_model,
            )

    def analyze(
        self,
        query: str,
        *,
        clarification_option: Optional[str] = None,
        clarification_state: Optional[dict] = None,
    ) -> AnalyzerResult:
        if not self.llm_client:
            result = self._fallback_result()
            return asyncio.run(self._apply_clarification_choice(result, clarification_option, clarification_state))
        clarifications = []
        try:
            prompt = self._build_prompt(query)
            response = self.llm_client.client.models.generate_content(
                model=self.llm_client.models[0],
                contents=[{"role": "user", "parts": [{"text": prompt}]}],
            )
            text = getattr(response, "text", "") or ""
            filters, summaries = self._parse_response(text)
            filters, clarifications = asyncio.run(self._normalize_with_metadata(filters))
            if not filters and clarifications:
                result = AnalyzerResult(
                    filters=[],
                    summaries=[],
                    success=True,
                    confidence="low",
                    clarification_needed=True,
                    clarification=clarifications[0],
                    known_context={},
                )
                return asyncio.run(
                    self._apply_clarification_choice(result, clarification_option, clarification_state)
                )
            if not filters:
                result = self._fallback_result(message="LLM 필터 추출 실패. 기본 필터 적용")
                return asyncio.run(
                    self._apply_clarification_choice(result, clarification_option, clarification_state)
                )
            result = AnalyzerResult(
                filters=filters,
                summaries=summaries,
                success=True,
                confidence="medium" if not clarifications else "low",
                clarification_needed=bool(clarifications),
                clarification=clarifications[0] if clarifications else None,
                known_context={},
            )
            return asyncio.run(
                self._apply_clarification_choice(result, clarification_option, clarification_state)
            )
        except Exception:
            result = self._fallback_result(message="LLM 호출 실패. 기본 필터 적용")
            return asyncio.run(
                self._apply_clarification_choice(result, clarification_option, clarification_state)
            )

    def _build_prompt(self, query: str) -> str:
        return (
            "사용자 질문에서 티켓 검색 조건을 JSON 배열로 출력하세요.\n"
            "필드 예: priority, status, requester, createdAt 등.\n"
            "반드시 아래 구조로만 응답: {\"filters\": [{\"field\":..., \"operator\":..., \"value\":...}], \"summaries\": []}.\n"
            f"질문: {query}"
        )

    def _parse_response(self, text: str) -> Tuple[List[MetadataFilter], List[str]]:
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            return [], []
        filters_data = payload.get("filters") or []
        summaries = payload.get("summaries") or []
        filters: List[MetadataFilter] = []
        for entry in filters_data:
            field = entry.get("field")
            value = entry.get("value")
            if not field or value is None:
                continue
            operator = entry.get("operator", "EQUALS").upper()
            if operator not in {"EQUALS", "GREATER_THAN", "LESS_THAN", "IN"}:
                operator = "EQUALS"
            filters.append(MetadataFilter(key=field, operator=operator, value=str(value)))
        return filters, summaries

    async def _normalize_with_metadata(self, filters: List[MetadataFilter]) -> Tuple[List[MetadataFilter], List[AnalyzerClarification]]:
        normalized: List[MetadataFilter] = []
        clarifications: List[AnalyzerClarification] = []
        for filter_ in filters:
            if filter_.key == "priority":
                code = await self.metadata_service.resolve_priority_label(filter_.value)
                if code is not None:
                    normalized.append(MetadataFilter(key="priority", operator="EQUALS", value=str(code)))
                    continue
                options = await self.metadata_service.list_priority_labels()
                clarifications.append(
                    AnalyzerClarification(
                        reason="INVALID_PRIORITY",
                        message="인식할 수 없는 우선순위입니다. 아래 옵션 중에서 선택해 주세요.",
                        options=options,
                        field="priority",
                    )
                )
                continue
            if filter_.key == "status":
                code = await self.metadata_service.resolve_status_label(filter_.value)
                if code is not None:
                    normalized.append(MetadataFilter(key="status", operator="EQUALS", value=str(code)))
                    continue
                options = await self.metadata_service.list_status_labels()
                clarifications.append(
                    AnalyzerClarification(
                        reason="INVALID_STATUS",
                        message="인식할 수 없는 상태 값입니다. 아래 옵션 중에서 선택해 주세요.",
                        options=options,
                        field="status",
                    )
                )
                continue
            normalized.append(filter_)
        return normalized, clarifications

    def _fallback_result(self, message: str = "필터를 아직 추출하지 못했습니다. 기본 기간 필터 적용") -> AnalyzerResult:
        fallback_filter = self._build_recent_filter()
        summaries = [f"기간=최근 {self.fallback_months}개월 (자동 적용)"]
        return AnalyzerResult(
            filters=[fallback_filter],
            summaries=summaries,
            success=True,
            confidence="low",
            clarification_needed=True,
            clarification=AnalyzerClarification(message=message),
            known_context={},
        )

    def _build_recent_filter(self) -> MetadataFilter:
        cutoff = datetime.now(timezone.utc) - timedelta(days=self.fallback_months * 30)
        return MetadataFilter(
            key="createdAt",
            operator="GREATER_THAN",
            value=cutoff.isoformat(),
        )

    async def _apply_clarification_choice(
        self,
        result: AnalyzerResult,
        clarification_option: Optional[str],
        clarification_state: Optional[dict],
    ) -> AnalyzerResult:
        if not clarification_option or not clarification_state:
            return result
        payload = self._extract_clarification_payload(clarification_state)
        if not payload:
            return result
        field = payload.get("field") or self._reason_to_field(payload.get("reason"))
        if not field:
            return result
        option_value = clarification_option.strip()
        if not option_value:
            return result
        filter_from_choice = await self._build_filter_from_choice(field, option_value)
        if not filter_from_choice:
            return result
        result.filters = [f for f in result.filters if f.key != filter_from_choice.key]
        result.filters.append(filter_from_choice)
        label = field.capitalize()
        summary = f"{label}={option_value}"
        result.summaries.append(summary)
        result.clarification_needed = False
        result.clarification = None
        result.confidence = "medium"
        result.known_context[field] = option_value
        return result

    def _extract_clarification_payload(self, state: dict) -> Optional[Dict[str, str]]:
        if not isinstance(state, dict):
            return None
        payload = state.get("clarification") or state.get("clarifications") or state
        if isinstance(payload, list) and payload:
            payload = payload[0]
        if not isinstance(payload, dict):
            return None
        return {
            "reason": payload.get("reason"),
            "field": payload.get("field"),
        }

    def _reason_to_field(self, reason: Optional[str]) -> Optional[str]:
        mapping = {
            "INVALID_PRIORITY": "priority",
            "INVALID_STATUS": "status",
        }
        return mapping.get(reason) if reason else None

    async def _build_filter_from_choice(self, field: str, option_value: str) -> Optional[MetadataFilter]:
        if field == "priority":
            code = await self.metadata_service.resolve_priority_label(option_value)
            if code is None:
                return None
            return MetadataFilter(key="priority", operator="EQUALS", value=str(code))
        if field == "status":
            code = await self.metadata_service.resolve_status_label(option_value)
            if code is None:
                return None
            return MetadataFilter(key="status", operator="EQUALS", value=str(code))
        return None


@lru_cache
def get_query_filter_analyzer() -> Optional[QueryFilterAnalyzer]:
    settings = get_settings()
    api_key = settings.gemini_api_key or os.getenv("GEMINI_API_KEY")
    if not api_key:
        return None
    return QueryFilterAnalyzer()
