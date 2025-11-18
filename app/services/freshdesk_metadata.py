from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from fastapi import HTTPException, status

from app.core.config import get_settings

logger = logging.getLogger(__name__)


@dataclass
class FreshdeskTicketFieldChoice:
    value: int
    label: str


@dataclass
class FreshdeskTicketField:
    name: str
    choices: Optional[List[FreshdeskTicketFieldChoice]] = None


@dataclass
class FreshdeskMetadataCache:
    status_map: Dict[int, str] = field(default_factory=dict)
    priority_map: Dict[int, str] = field(default_factory=dict)
    source_map: Dict[int, str] = field(default_factory=dict)
    type_map: Dict[str, str] = field(default_factory=dict)
    expires_at: datetime = field(default_factory=lambda: datetime.utcnow())


class FreshdeskMetadataService:
    def __init__(self, *, ttl_hours: int = 24) -> None:
        self.ttl = timedelta(hours=ttl_hours)
        self.cache: Optional[FreshdeskMetadataCache] = None

    async def ensure_loaded(self) -> None:
        if self.cache and self.cache.expires_at > datetime.utcnow():
            return
        await self._load_metadata()

    async def _load_metadata(self) -> None:
        # TODO: 실제 Freshdesk API 연동 추가
        logger.info("Loading Freshdesk ticket field metadata (stub)")
        fields = [
            FreshdeskTicketField(
                name="status",
                choices=[
                    FreshdeskTicketFieldChoice(value=2, label="Open"),
                    FreshdeskTicketFieldChoice(value=3, label="Pending"),
                    FreshdeskTicketFieldChoice(value=4, label="Resolved"),
                    FreshdeskTicketFieldChoice(value=5, label="Closed"),
                ],
            ),
            FreshdeskTicketField(
                name="priority",
                choices=[
                    FreshdeskTicketFieldChoice(value=1, label="Low"),
                    FreshdeskTicketFieldChoice(value=2, label="Medium"),
                    FreshdeskTicketFieldChoice(value=3, label="High"),
                    FreshdeskTicketFieldChoice(value=4, label="Urgent"),
                ],
            ),
        ]

        cache = FreshdeskMetadataCache()
        for field in fields:
            if not field.choices:
                continue
            mapping = {choice.value: choice.label for choice in field.choices}
            if field.name == "status":
                cache.status_map = mapping
            elif field.name == "priority":
                cache.priority_map = mapping
        cache.expires_at = datetime.utcnow() + self.ttl
        self.cache = cache

    async def resolve_priority_label(self, label: str) -> Optional[int]:
        await self.ensure_loaded()
        normalized = label.strip().lower()
        reverse = {name.lower(): value for value, name in self.cache.priority_map.items()}
        return reverse.get(normalized)

    async def resolve_status_label(self, label: str) -> Optional[int]:
        await self.ensure_loaded()
        normalized = label.strip().lower()
        reverse = {name.lower(): value for value, name in self.cache.status_map.items()}
        return reverse.get(normalized)

    async def list_priority_labels(self) -> List[str]:
        await self.ensure_loaded()
        return list(self.cache.priority_map.values())

    async def list_status_labels(self) -> List[str]:
        await self.ensure_loaded()
        return list(self.cache.status_map.values())


metadata_service = FreshdeskMetadataService()
