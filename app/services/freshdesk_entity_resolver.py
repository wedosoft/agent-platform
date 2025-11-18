from __future__ import annotations

import logging
from dataclasses import asdict
from functools import lru_cache
from typing import List, Optional

from fastapi import HTTPException, status

from app.core.config import get_settings
from app.models.entity import EntityMatch, EntityResolutionResult
from app.services.freshdesk_client import FreshdeskClient, FreshdeskClientError

logger = logging.getLogger(__name__)


class FreshdeskEntityResolver:
    def __init__(self, client: Optional[FreshdeskClient] = None) -> None:
        self.client = client

    async def resolve(
        self,
        term: str,
        *,
        include_contacts: bool = True,
        include_agents: bool = True,
    ) -> EntityResolutionResult:
        term = term.strip()
        if not term:
            return EntityResolutionResult(matches=[], clarification_needed=True, reason="NO_MATCH")
        client = await self._ensure_client()
        matches: List[EntityMatch] = []
        if include_contacts:
            matches.extend(await self._search_contacts(client, term))
        if include_agents:
            matches.extend(await self._search_agents(client, term))

        if not matches:
            return EntityResolutionResult(matches=[], clarification_needed=True, reason="NO_MATCH")
        matches.sort(key=lambda m: m.confidence, reverse=True)
        if len(matches) == 1:
            return EntityResolutionResult(matches=matches, clarification_needed=False)
        return EntityResolutionResult(matches=matches[:5], clarification_needed=True, reason="AMBIGUOUS")

    async def _search_contacts(self, client: FreshdeskClient, term: str) -> List[EntityMatch]:
        try:
            response = await client.search_contacts(term)
        except FreshdeskClientError as exc:  # pragma: no cover - network errors
            logger.warning("Freshdesk contact search failed: %s", exc)
            return []
        matches: List[EntityMatch] = []
        for raw in response.get("results", []):
            matches.append(
                EntityMatch(
                    id=raw.get("id"),
                    type="contact",
                    name=raw.get("name") or raw.get("email") or "Unknown",
                    email=raw.get("email"),
                    confidence=1.0,
                    source="exact",
                    details={"raw": raw},
                )
            )
        return matches

    async def _search_agents(self, client: FreshdeskClient, term: str) -> List[EntityMatch]:
        try:
            response = await client.search_agents(term)
        except FreshdeskClientError as exc:  # pragma: no cover
            logger.warning("Freshdesk agent search failed: %s", exc)
            return []
        matches: List[EntityMatch] = []
        for raw in response.get("results", []):
            matches.append(
                EntityMatch(
                    id=raw.get("id"),
                    type="agent",
                    name=raw.get("name") or raw.get("email") or "Agent",
                    email=raw.get("email"),
                    confidence=1.0,
                    source="exact",
                    details={"raw": raw},
                )
            )
        return matches

    async def _ensure_client(self) -> FreshdeskClient:
        if self.client:
            return self.client
        settings = get_settings()
        if not settings.freshdesk_domain or not settings.freshdesk_api_key:
            raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Freshdesk API 설정이 필요합니다")
        self.client = FreshdeskClient(settings.freshdesk_domain, settings.freshdesk_api_key)
        return self.client


@lru_cache
def get_freshdesk_entity_resolver() -> Optional[FreshdeskEntityResolver]:
    settings = get_settings()
    if not settings.freshdesk_domain or not settings.freshdesk_api_key:
        return None
    client = FreshdeskClient(settings.freshdesk_domain, settings.freshdesk_api_key)
    return FreshdeskEntityResolver(client=client)
