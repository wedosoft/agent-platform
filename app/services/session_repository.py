from __future__ import annotations

import json
from abc import ABC, abstractmethod
from datetime import datetime, timedelta, timezone
from dataclasses import asdict
from typing import Any, Dict, Optional

from fastapi import HTTPException, status
from redis import Redis

from app.core.config import get_settings
from app.models.analyzer import AnalyzerResult


SessionRecord = Dict[str, Any]


class SessionRepository(ABC):
    def __init__(self, ttl_seconds: int) -> None:
        self.ttl_seconds = ttl_seconds

    @abstractmethod
    def save(self, record: SessionRecord) -> SessionRecord:
        ...

    @abstractmethod
    def get(self, session_id: str) -> Optional[SessionRecord]:
        ...

    @abstractmethod
    def append_question(self, session_id: str, question: str) -> Optional[SessionRecord]:
        ...

    @abstractmethod
    def record_analyzer_result(self, session_id: str, result: AnalyzerResult) -> None:
        ...

    def normalize(self, payload: Dict[str, Any]) -> SessionRecord:
        now = datetime.now(timezone.utc).isoformat()
        record: SessionRecord = dict(payload)
        record.setdefault("createdAt", now)
        record.setdefault("updatedAt", record.get("createdAt", now))
        record.setdefault("questionHistory", [])
        return record


class InMemorySessionRepository(SessionRepository):
    def __init__(self, ttl_seconds: int) -> None:
        super().__init__(ttl_seconds)
        self._data: Dict[str, SessionRecord] = {}
        self._expires: Dict[str, datetime] = {}

    def _purge(self) -> None:
        now = datetime.now(timezone.utc)
        expired = [session_id for session_id, exp in self._expires.items() if exp <= now]
        for session_id in expired:
            self._data.pop(session_id, None)
            self._expires.pop(session_id, None)

    def _touch(self, session_id: str) -> None:
        self._expires[session_id] = datetime.now(timezone.utc) + timedelta(seconds=self.ttl_seconds)

    def save(self, record: SessionRecord) -> SessionRecord:
        self._purge()
        session_id = record["sessionId"]
        record = self.normalize(record)
        self._data[session_id] = record
        self._touch(session_id)
        return record

    def get(self, session_id: str) -> Optional[SessionRecord]:
        self._purge()
        record = self._data.get(session_id)
        if record:
            self._touch(session_id)
        return record

    def append_question(self, session_id: str, question: str) -> Optional[SessionRecord]:
        record = self.get(session_id)
        if not record:
            return None
        history = record.setdefault("questionHistory", [])
        history.append(question)
        record["updatedAt"] = datetime.now(timezone.utc).isoformat()
        self.save(record)
        return record

    def record_analyzer_result(self, session_id: str, result: AnalyzerResult) -> None:
        record = self.get(session_id)
        if not record:
            return
        responses = record.setdefault("analyzerResponses", [])
        snapshot = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "filters": [asdict(filter_) for filter_ in result.filters],
            "summaries": result.summaries,
            "confidence": result.confidence,
            "clarificationNeeded": result.clarification_needed,
            "clarification": asdict(result.clarification) if result.clarification else None,
        }
        responses.append(snapshot)
        record["knownContext"] = result.known_context
        if result.clarification_needed:
            record["clarificationState"] = {
                "message": result.clarification.message if result.clarification else None,
                "options": result.clarification.options if result.clarification else None,
            }
        self.save(record)


class RedisSessionRepository(SessionRepository):
    def __init__(self, redis_client: Redis, prefix: str, ttl_seconds: int) -> None:
        super().__init__(ttl_seconds)
        self.client = redis_client
        self.prefix = prefix

    def _key(self, session_id: str) -> str:
        return f"{self.prefix}:{session_id}"

    def save(self, record: SessionRecord) -> SessionRecord:
        record = self.normalize(record)
        key = self._key(record["sessionId"])
        self.client.setex(key, self.ttl_seconds, json.dumps(record))
        return record

    def get(self, session_id: str) -> Optional[SessionRecord]:
        raw = self.client.get(self._key(session_id))
        if not raw:
            return None
        record = json.loads(raw)
        # touch TTL
        self.client.expire(self._key(session_id), self.ttl_seconds)
        return record

    def append_question(self, session_id: str, question: str) -> Optional[SessionRecord]:
        record = self.get(session_id)
        if not record:
            return None
        history = record.setdefault("questionHistory", [])
        history.append(question)
        record["updatedAt"] = datetime.now(timezone.utc).isoformat()
        self.save(record)
        return record

    def record_analyzer_result(self, session_id: str, result: AnalyzerResult) -> None:
        record = self.get(session_id)
        if not record:
            return
        responses = record.setdefault("analyzerResponses", [])
        snapshot = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "filters": [asdict(filter_) for filter_ in result.filters],
            "summaries": result.summaries,
            "confidence": result.confidence,
            "clarificationNeeded": result.clarification_needed,
            "clarification": asdict(result.clarification) if result.clarification else None,
        }
        responses.append(snapshot)
        record["knownContext"] = result.known_context
        if result.clarification_needed:
            record["clarificationState"] = {
                "message": result.clarification.message if result.clarification else None,
                "options": result.clarification.options if result.clarification else None,
            }
        self.save(record)


def _build_redis_client(url: str) -> Redis:
    try:
        return Redis.from_url(url, decode_responses=True)
    except Exception as exc:  # pragma: no cover
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Redis 연결 실패: {exc}") from exc


def get_session_repository() -> SessionRepository:
    settings = get_settings()
    ttl_seconds = settings.session_ttl_minutes * 60
    if settings.redis_url:
        client = _build_redis_client(settings.redis_url)
        return RedisSessionRepository(client, settings.redis_session_prefix, ttl_seconds)
    return InMemorySessionRepository(ttl_seconds)
