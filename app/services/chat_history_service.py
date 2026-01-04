"""대화 히스토리 서비스 - 인메모리 캐시 대체 영속화 레이어."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

from supabase import Client

from app.services.content_repository import (
    ChatMessage,
    ChatSummary,
    ContentRepository,
    get_content_repository,
)

LOGGER = logging.getLogger(__name__)

MAX_HISTORY_TURNS = 10


class ChatHistoryService:
    """대화 히스토리 서비스 (영속화 + 캐싱)."""

    def __init__(self, client: Client) -> None:
        self.content_repo = get_content_repository(client)
        self._local_cache: Dict[str, List[Dict[str, str]]] = {}

    def _get_cache_key(
        self,
        session_id: str,
        context_type: str = "mentor",
        context_id: Optional[str] = None,
    ) -> str:
        """캐시 키 생성."""
        return f"{session_id}:{context_type}:{context_id or 'default'}"

    async def get_conversation_history(
        self,
        session_id: str,
        context_type: str = "mentor",
        context_id: Optional[str] = None,
        limit: int = MAX_HISTORY_TURNS,
    ) -> List[Dict[str, str]]:
        """대화 히스토리 조회 (DB 우선, 로컬 캐시 폴백)."""
        cache_key = self._get_cache_key(session_id, context_type, context_id)
        
        try:
            messages = await self.content_repo.get_chat_history(
                session_id=session_id,
                context_type=context_type,
                context_id=context_id,
                limit=limit,
            )
            
            history = [
                {"role": msg.role, "parts": [{"text": msg.content}]}
                for msg in messages
            ]
            
            self._local_cache[cache_key] = history
            return history
            
        except Exception as e:
            LOGGER.warning(f"Failed to get chat history from DB, using cache: {e}")
            return self._local_cache.get(cache_key, [])

    async def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        context_type: str = "mentor",
        context_id: Optional[str] = None,
    ) -> None:
        """대화 메시지 추가."""
        cache_key = self._get_cache_key(session_id, context_type, context_id)
        
        if cache_key not in self._local_cache:
            self._local_cache[cache_key] = []
        self._local_cache[cache_key].append({
            "role": role,
            "parts": [{"text": content}],
        })
        
        if len(self._local_cache[cache_key]) > MAX_HISTORY_TURNS * 2:
            self._local_cache[cache_key] = self._local_cache[cache_key][-MAX_HISTORY_TURNS * 2:]
        
        try:
            await self.content_repo.add_chat_message(
                session_id=session_id,
                role=role,
                content=content,
                context_type=context_type,
                context_id=context_id,
            )
        except Exception as e:
            LOGGER.warning(f"Failed to persist chat message: {e}")

    async def add_user_message(
        self,
        session_id: str,
        content: str,
        context_type: str = "mentor",
        context_id: Optional[str] = None,
    ) -> None:
        """사용자 메시지 추가."""
        await self.add_message(session_id, "user", content, context_type, context_id)

    async def add_model_message(
        self,
        session_id: str,
        content: str,
        context_type: str = "mentor",
        context_id: Optional[str] = None,
    ) -> None:
        """모델 응답 추가."""
        await self.add_message(session_id, "model", content, context_type, context_id)

    async def clear_history(
        self,
        session_id: str,
        context_type: str = "mentor",
        context_id: Optional[str] = None,
    ) -> None:
        """대화 히스토리 삭제."""
        cache_key = self._get_cache_key(session_id, context_type, context_id)
        
        if cache_key in self._local_cache:
            del self._local_cache[cache_key]
        
        try:
            await self.content_repo.clear_chat_history(
                session_id=session_id,
                context_type=context_type,
                context_id=context_id,
            )
        except Exception as e:
            LOGGER.warning(f"Failed to clear chat history from DB: {e}")

    async def get_or_create_history(
        self,
        session_id: str,
        context_type: str = "mentor",
        context_id: Optional[str] = None,
    ) -> List[Dict[str, str]]:
        """대화 히스토리 조회 또는 빈 리스트 반환."""
        history = await self.get_conversation_history(
            session_id, context_type, context_id
        )
        return history if history else []

    def get_history_for_gemini(
        self,
        session_id: str,
        context_type: str = "mentor",
        context_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Gemini API 형식의 대화 히스토리 반환 (동기, 캐시만 사용)."""
        cache_key = self._get_cache_key(session_id, context_type, context_id)
        return self._local_cache.get(cache_key, [])

    async def get_conversation_summary(
        self,
        session_id: str,
        context_type: str = "mentor",
        context_id: Optional[str] = None,
    ) -> Optional[str]:
        """대화 요약 조회."""
        try:
            summary = await self.content_repo.get_chat_summary(
                session_id=session_id,
                context_type=context_type,
                context_id=context_id,
            )
            return summary.summary if summary else None
        except Exception as e:
            LOGGER.warning(f"Failed to get chat summary: {e}")
            return None


_chat_history_service: Optional[ChatHistoryService] = None


def get_chat_history_service(client: Client) -> ChatHistoryService:
    """ChatHistoryService 인스턴스 반환."""
    global _chat_history_service
    if _chat_history_service is None:
        _chat_history_service = ChatHistoryService(client)
    return _chat_history_service


def reset_chat_history_service() -> None:
    """ChatHistoryService 인스턴스 초기화 (테스트용)."""
    global _chat_history_service
    _chat_history_service = None
