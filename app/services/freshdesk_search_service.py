from __future__ import annotations

import logging
from dataclasses import dataclass
from functools import lru_cache
from typing import Dict, List, Optional

from fastapi import HTTPException, status

from app.core.config import get_settings
from app.models.analyzer import AnalyzerResult
from app.models.metadata import MetadataFilter
from app.services.freshdesk_client import FreshdeskClient, FreshdeskClientError
from app.services.freshdesk_entity_resolver import FreshdeskEntityResolver, get_freshdesk_entity_resolver
from app.services.freshdesk_metadata import FreshdeskMetadataService, get_freshdesk_metadata_service

logger = logging.getLogger(__name__)


@dataclass
class FreshdeskSearchResult:
    ticket_ids: List[int]
    total: int
    query_string: str
    tickets: List[dict]
    plan: Dict[str, List[dict]]


class FreshdeskSearchService:
    def __init__(
        self,
        *,
        client: Optional[FreshdeskClient] = None,
        entity_resolver: Optional[FreshdeskEntityResolver] = None,
        metadata_service: Optional[FreshdeskMetadataService] = None,
    ) -> None:
        self.client = client
        self.entity_resolver = entity_resolver
        self.metadata_service = metadata_service or get_freshdesk_metadata_service()

    async def search_with_filters(self, analyzer_result: AnalyzerResult) -> FreshdeskSearchResult:
        plan = self._build_plan()
        query_expr = await self._build_query(analyzer_result, plan)
        if not query_expr:
            return FreshdeskSearchResult(ticket_ids=[], total=0, query_string="", tickets=[], plan=plan)
        client = await self._ensure_client()
        logger.info("Freshdesk search query=%s", query_expr)
        try:
            data = await client.search_tickets(query_expr)
        except FreshdeskClientError as exc:  # pragma: no cover - network errors
            raise HTTPException(status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
        tickets = data.get("results", [])
        ids = [ticket.get("id") for ticket in tickets if ticket.get("id")]
        summaries = [self._summarize_ticket(ticket) for ticket in tickets]
        return FreshdeskSearchResult(
            ticket_ids=ids,
            total=data.get("total", len(ids)),
            query_string=query_expr,
            tickets=summaries,
            plan=plan,
        )

    async def _ensure_client(self) -> FreshdeskClient:
        if self.client:
            return self.client
        settings = get_settings()
        if not settings.freshdesk_domain or not settings.freshdesk_api_key:
            raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Freshdesk API 설정이 필요합니다")
        self.client = FreshdeskClient(settings.freshdesk_domain, settings.freshdesk_api_key)
        return self.client

    def _build_plan(self) -> Dict[str, List[dict]]:
        return {
            "appliedFilters": [],
            "skippedFilters": [],
            "entityMappings": [],
        }

    async def _build_query(self, analyzer_result: AnalyzerResult, plan: Dict[str, List[dict]]) -> Optional[str]:
        parts: List[str] = []
        for filter_ in analyzer_result.filters:
            expression = await self._translate_filter(filter_, plan)
            if expression:
                parts.append(expression)
        context_parts = await self._build_context_filters(analyzer_result.known_context or {}, plan)
        parts.extend(context_parts)
        return " AND ".join(parts) if parts else None

    async def _translate_filter(self, filter_: MetadataFilter, plan: Dict[str, List[dict]]) -> Optional[str]:
        entry = {
            "key": filter_.key,
            "value": filter_.value,
            "operator": filter_.operator,
        }
        key = filter_.key
        expression: Optional[str] = None
        if key in {"priority", "status"}:
            expression = f"{key}:{filter_.value}"
        elif key in {"createdAt", "updatedAt"}:
            expression = self._build_date_expression(key, filter_)
        elif key in {"requesterId", "requester_id"}:
            expression = f"requester_id:{filter_.value}"
        elif key in {"responderId", "responder_id"}:
            expression = f"responder_id:{filter_.value}"
        elif key in {"category", "categoryId", "category_id"}:
            resolved = await self._resolve_category(filter_.value)
            if resolved is not None:
                expression = f"category_id:{resolved}"
            else:
                entry["reason"] = "CATEGORY_NOT_FOUND"
        elif key in {"folder", "folderId", "folder_id"}:
            resolved = await self._resolve_folder(filter_.value)
            if resolved is not None:
                expression = f"folder_id:{resolved}"
            else:
                entry["reason"] = "FOLDER_NOT_FOUND"
        elif key in {"group", "groupId", "group_id"}:
            expression = f"group_id:{filter_.value}"
        else:
            entry["reason"] = "UNSUPPORTED_FIELD"

        if expression:
            entry["expression"] = expression
            entry["source"] = "analyzer"
            plan["appliedFilters"].append(entry)
            return expression

        plan["skippedFilters"].append(entry)
        return None

    async def _build_context_filters(self, context: dict, plan: Dict[str, List[dict]]) -> List[str]:
        if not context:
            return []
        resolver = self.entity_resolver or get_freshdesk_entity_resolver()
        if not resolver:
            plan["entityMappings"].append({"status": "resolver_unavailable", "context": context})
            return []
        expressions: List[str] = []
        contact_term = context.get("contactQuery") or context.get("requester")
        if contact_term:
            expr = await self._resolve_entity(resolver, contact_term, target_field="requester_id", entity_type="contact", plan=plan)
            if expr:
                expressions.append(expr)
        agent_term = context.get("agentQuery") or context.get("assignee")
        if agent_term:
            expr = await self._resolve_entity(resolver, agent_term, target_field="responder_id", entity_type="agent", plan=plan)
            if expr:
                expressions.append(expr)
        return expressions

    async def _resolve_entity(
        self,
        resolver: FreshdeskEntityResolver,
        term: str,
        *,
        target_field: str,
        entity_type: str,
        plan: Dict[str, List[dict]],
    ) -> Optional[str]:
        try:
            include_contacts = entity_type == "contact"
            include_agents = entity_type == "agent"
            results = await resolver.resolve(term, include_contacts=include_contacts, include_agents=include_agents)
        except HTTPException:  # pragma: no cover - propagate API errors
            return None
        entry = {
            "term": term,
            "type": entity_type,
            "clarificationNeeded": results.clarification_needed,
        }
        if results.matches:
            first = results.matches[0]
            entry["match"] = {"id": first.id, "name": first.name, "confidence": first.confidence}
            if not results.clarification_needed:
                expression = f"{target_field}:{first.id}"
                entry["expression"] = expression
                plan["entityMappings"].append(entry)
                return expression
        plan["entityMappings"].append(entry)
        return None

    def _build_date_expression(self, field: str, filter_: MetadataFilter) -> Optional[str]:
        target_field = "created_at" if field == "createdAt" else "updated_at"
        value = filter_.value
        if filter_.operator == "GREATER_THAN":
            return f"{target_field}:>'{value}'"
        if filter_.operator == "LESS_THAN":
            return f"{target_field}:<'{value}'"
        if filter_.operator == "IN":
            values = [v.strip() for v in value.split(",") if v.strip()]
            if not values:
                return None
            parts = [f"{target_field}:{val}" for val in values]
            return "(" + " OR ".join(parts) + ")"
        return f"{target_field}:{value}"

    async def _resolve_category(self, label: str) -> Optional[int]:
        if label.isdigit():
            return int(label)
        return await self.metadata_service.resolve_category_id(label)

    async def _resolve_folder(self, label: str) -> Optional[int]:
        if label.isdigit():
            return int(label)
        return await self.metadata_service.resolve_folder_id(label)

    def _summarize_ticket(self, ticket: dict) -> dict:
        requester = self._extract_name(ticket.get("requester"), ticket.get("requester_name"))
        responder = self._extract_name(ticket.get("responder"), ticket.get("responder_name"))
        description = ticket.get("description_text") or ""
        preview = self._build_preview(description)
        summary = {
            "id": ticket.get("id"),
            "subject": ticket.get("subject"),
            "status": ticket.get("status_name") or ticket.get("status"),
            "priority": ticket.get("priority_name") or ticket.get("priority"),
            "requester": requester,
            "responder": responder,
            "updatedAt": ticket.get("updated_at"),
        }
        if preview:
            summary["description"] = preview
        return summary

    def _extract_name(self, payload, fallback: Optional[str]) -> Optional[str]:
        if isinstance(payload, dict):
            return payload.get("name") or payload.get("email") or fallback
        return fallback

    def _build_preview(self, description: str) -> Optional[str]:
        text = (description or "").strip().replace("\n", " ")
        if not text:
            return None
        return text[:200]


@lru_cache
def get_freshdesk_search_service() -> Optional[FreshdeskSearchService]:
    settings = get_settings()
    if not settings.freshdesk_domain or not settings.freshdesk_api_key:
        return None
    client = FreshdeskClient(settings.freshdesk_domain, settings.freshdesk_api_key)
    resolver = get_freshdesk_entity_resolver()
    metadata_service = get_freshdesk_metadata_service()
    return FreshdeskSearchService(client=client, entity_resolver=resolver, metadata_service=metadata_service)
