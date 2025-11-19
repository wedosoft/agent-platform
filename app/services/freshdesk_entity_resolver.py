from __future__ import annotations

import json
import logging
from dataclasses import asdict
from functools import lru_cache
from typing import List, Optional

from fastapi import HTTPException, status
import redis.asyncio as redis

from app.core.config import get_settings
from app.models.entity import EntityMatch, EntityResolutionResult
from app.services.freshdesk_client import FreshdeskClient, FreshdeskClientError

logger = logging.getLogger(__name__)


class FreshdeskEntityResolver:
    def __init__(
        self,
        client: Optional[FreshdeskClient] = None,
        redis_client: Optional[redis.Redis] = None,
    ) -> None:
        self.client = client
        self.redis = redis_client
        self.ttl_seconds = 3600  # 1 hour

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
        
        cache_key = f"freshdesk:entity:{term}"
        
        # Try cache first
        if self.redis:
            try:
                cached = await self.redis.get(cache_key)
                if cached:
                    data = json.loads(cached)
                    # Reconstruct matches
                    matches_data = data.get("matches", [])
                    matches = [EntityMatch(**m) for m in matches_data]
                    return EntityResolutionResult(
                        matches=matches,
                        clarification_needed=data.get("clarification_needed", False),
                        reason=data.get("reason")
                    )
            except Exception as e:
                logger.warning(f"Entity cache read failed: {e}")

        client = await self._ensure_client()
        matches: List[EntityMatch] = []
        if include_contacts:
            matches.extend(await self._search_contacts(client, term))
        if include_agents:
            matches.extend(await self._search_agents(client, term))

        result: EntityResolutionResult
        if not matches:
            result = EntityResolutionResult(matches=[], clarification_needed=True, reason="NO_MATCH")
        else:
            matches.sort(key=lambda m: m.confidence, reverse=True)
            if len(matches) == 1:
                result = EntityResolutionResult(matches=matches, clarification_needed=False)
            else:
                result = EntityResolutionResult(matches=matches[:5], clarification_needed=True, reason="AMBIGUOUS")

        # Save to cache
        if self.redis:
            try:
                # dataclasses.asdict works for dataclasses, but EntityMatch might be Pydantic.
                # Assuming dataclasses based on previous code using asdict.
                # If they are Pydantic models, .model_dump() or .dict() should be used.
                # Let's assume they are dataclasses as per import `from dataclasses import asdict`.
                # Wait, previous code imported `asdict` but I haven't seen `EntityMatch` definition yet.
                # I will use a helper that tries both.
                payload = {
                    "matches": [asdict(m) if hasattr(m, "__dataclass_fields__") else m.dict() for m in result.matches],
                    "clarification_needed": result.clarification_needed,
                    "reason": result.reason,
                }
                await self.redis.setex(cache_key, self.ttl_seconds, json.dumps(payload))
            except Exception as e:
                logger.warning(f"Entity cache write failed: {e}")
        
        return result

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
    
    redis_client = None
    if settings.redis_url:
        try:
            redis_client = redis.from_url(settings.redis_url, decode_responses=True)
        except Exception as e:
            logger.warning(f"Failed to connect to Redis for entity resolver: {e}")

    return FreshdeskEntityResolver(client=client, redis_client=redis_client)
