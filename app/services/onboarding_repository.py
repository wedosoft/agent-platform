"""온보딩 진행도 저장소 - Supabase 연동."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from functools import lru_cache
from typing import Any, Dict, List, Optional

from supabase import Client, ClientOptions, create_client

from app.core.config import get_settings
from app.models.onboarding import (
    OnboardingProgress,
    OnboardingProgressSummary,
    OnboardingSession,
)

LOGGER = logging.getLogger(__name__)

# Supabase 테이블명
TABLE_SESSIONS = "onboarding_sessions"
TABLE_PROGRESS = "onboarding_progress"


class OnboardingRepositoryError(RuntimeError):
    """온보딩 저장소 에러."""
    pass


class OnboardingRepository:
    """온보딩 세션 및 진행도 저장소 (Supabase 기반)."""

    def __init__(self, client: Client) -> None:
        self.client = client

    # ============================================
    # 세션 관리
    # ============================================

    async def create_session(self, session_id: str, user_name: str) -> OnboardingSession:
        """새 온보딩 세션 생성."""
        now = datetime.now(timezone.utc).isoformat()
        data = {
            "session_id": session_id,
            "user_name": user_name,
            "created_at": now,
            "updated_at": now,
        }

        try:
            response = self.client.table(TABLE_SESSIONS).insert(data).execute()
            if response.data:
                row = response.data[0]
                return OnboardingSession(
                    id=row.get("id"),
                    sessionId=row["session_id"],
                    userName=row["user_name"],
                    createdAt=row.get("created_at"),
                    updatedAt=row.get("updated_at"),
                )
            raise OnboardingRepositoryError("Failed to create session")
        except Exception as e:
            LOGGER.error(f"Failed to create onboarding session: {e}")
            raise OnboardingRepositoryError(str(e)) from e

    async def get_session(self, session_id: str) -> Optional[OnboardingSession]:
        """세션 조회."""
        try:
            response = (
                self.client.table(TABLE_SESSIONS)
                .select("*")
                .eq("session_id", session_id)
                .limit(1)
                .execute()
            )
            if response.data:
                row = response.data[0]
                return OnboardingSession(
                    id=row.get("id"),
                    sessionId=row["session_id"],
                    userName=row["user_name"],
                    createdAt=row.get("created_at"),
                    updatedAt=row.get("updated_at"),
                )
            return None
        except Exception as e:
            LOGGER.error(f"Failed to get onboarding session: {e}")
            return None

    async def get_or_create_session(self, session_id: str, user_name: str) -> OnboardingSession:
        """세션 조회 또는 생성."""
        session = await self.get_session(session_id)
        if session:
            return session
        return await self.create_session(session_id, user_name)

    # ============================================
    # 진행도 관리
    # ============================================

    async def save_progress(
        self,
        session_id: str,
        scenario_id: str,
        choice_id: str,
        feedback_rating: Optional[int] = None,
    ) -> OnboardingProgress:
        """시나리오 진행도 저장 (upsert)."""
        now = datetime.now(timezone.utc).isoformat()
        data = {
            "session_id": session_id,
            "scenario_id": scenario_id,
            "choice_id": choice_id,
            "feedback_rating": feedback_rating,
            "completed_at": now,
        }

        try:
            # Upsert: session_id + scenario_id 조합으로 중복 방지
            response = (
                self.client.table(TABLE_PROGRESS)
                .upsert(data, on_conflict="session_id,scenario_id")
                .execute()
            )
            if response.data:
                row = response.data[0]
                return OnboardingProgress(
                    id=row.get("id"),
                    sessionId=row["session_id"],
                    scenarioId=row["scenario_id"],
                    choiceId=row["choice_id"],
                    feedbackRating=row.get("feedback_rating"),
                    completedAt=row.get("completed_at"),
                )
            raise OnboardingRepositoryError("Failed to save progress")
        except Exception as e:
            LOGGER.error(f"Failed to save onboarding progress: {e}")
            raise OnboardingRepositoryError(str(e)) from e

    async def get_progress(self, session_id: str) -> List[OnboardingProgress]:
        """세션의 모든 진행도 조회."""
        try:
            response = (
                self.client.table(TABLE_PROGRESS)
                .select("*")
                .eq("session_id", session_id)
                .order("completed_at", desc=False)
                .execute()
            )
            return [
                OnboardingProgress(
                    id=row.get("id"),
                    sessionId=row["session_id"],
                    scenarioId=row["scenario_id"],
                    choiceId=row["choice_id"],
                    feedbackRating=row.get("feedback_rating"),
                    completedAt=row.get("completed_at"),
                )
                for row in (response.data or [])
            ]
        except Exception as e:
            LOGGER.error(f"Failed to get onboarding progress: {e}")
            return []

    async def get_progress_summary(
        self,
        session_id: str,
        total_scenarios: int = 12,
    ) -> OnboardingProgressSummary:
        """진행도 요약 조회."""
        session = await self.get_session(session_id)
        progress_list = await self.get_progress(session_id)

        user_name = session.user_name if session else "신입사원"
        completed_count = len(progress_list)
        completion_rate = (completed_count / total_scenarios * 100) if total_scenarios > 0 else 0.0

        return OnboardingProgressSummary(
            userId=session_id,
            userName=user_name,
            completedScenarios=progress_list,
            totalScenarios=total_scenarios,
            completionRate=round(completion_rate, 1),
        )

    # ============================================
    # 통계
    # ============================================

    async def get_all_sessions_summary(self) -> List[Dict[str, Any]]:
        """모든 세션의 진행도 요약 (관리자용)."""
        try:
            # 모든 세션 조회
            sessions_response = (
                self.client.table(TABLE_SESSIONS)
                .select("session_id, user_name, created_at")
                .order("created_at", desc=True)
                .execute()
            )

            summaries = []
            for session_row in (sessions_response.data or []):
                session_id = session_row["session_id"]
                progress_list = await self.get_progress(session_id)

                summaries.append({
                    "sessionId": session_id,
                    "userName": session_row["user_name"],
                    "createdAt": session_row["created_at"],
                    "completedCount": len(progress_list),
                    "totalScenarios": 12,
                    "completionRate": round(len(progress_list) / 12 * 100, 1),
                })

            return summaries
        except Exception as e:
            LOGGER.error(f"Failed to get all sessions summary: {e}")
            return []


# ============================================
# 팩토리 함수
# ============================================

def _build_supabase_client() -> Optional[Client]:
    """Supabase 클라이언트 생성."""
    settings = get_settings()
    if not settings.supabase_common_url or not settings.supabase_common_service_role_key:
        LOGGER.warning("Supabase configuration not found, using in-memory fallback")
        return None
    return create_client(
        settings.supabase_common_url,
        settings.supabase_common_service_role_key,
        options=ClientOptions(schema="onboarding"),
    )


class InMemoryOnboardingRepository:
    """인메모리 폴백 저장소 (Supabase 미설정 시)."""

    def __init__(self) -> None:
        self._sessions: Dict[str, OnboardingSession] = {}
        self._progress: Dict[str, List[OnboardingProgress]] = {}

    async def create_session(self, session_id: str, user_name: str) -> OnboardingSession:
        now = datetime.now(timezone.utc)
        session = OnboardingSession(
            sessionId=session_id,
            userName=user_name,
            createdAt=now,
            updatedAt=now,
        )
        self._sessions[session_id] = session
        return session

    async def get_session(self, session_id: str) -> Optional[OnboardingSession]:
        return self._sessions.get(session_id)

    async def get_or_create_session(self, session_id: str, user_name: str) -> OnboardingSession:
        if session_id in self._sessions:
            return self._sessions[session_id]
        return await self.create_session(session_id, user_name)

    async def save_progress(
        self,
        session_id: str,
        scenario_id: str,
        choice_id: str,
        feedback_rating: Optional[int] = None,
    ) -> OnboardingProgress:
        now = datetime.now(timezone.utc)
        progress = OnboardingProgress(
            sessionId=session_id,
            scenarioId=scenario_id,
            choiceId=choice_id,
            feedbackRating=feedback_rating,
            completedAt=now,
        )

        if session_id not in self._progress:
            self._progress[session_id] = []

        # 중복 제거 (같은 시나리오는 업데이트)
        existing = [p for p in self._progress[session_id] if p.scenario_id != scenario_id]
        existing.append(progress)
        self._progress[session_id] = existing

        return progress

    async def get_progress(self, session_id: str) -> List[OnboardingProgress]:
        return self._progress.get(session_id, [])

    async def get_progress_summary(
        self,
        session_id: str,
        total_scenarios: int = 12,
    ) -> OnboardingProgressSummary:
        session = await self.get_session(session_id)
        progress_list = await self.get_progress(session_id)

        user_name = session.user_name if session else "신입사원"
        completed_count = len(progress_list)
        completion_rate = (completed_count / total_scenarios * 100) if total_scenarios > 0 else 0.0

        return OnboardingProgressSummary(
            userId=session_id,
            userName=user_name,
            completedScenarios=progress_list,
            totalScenarios=total_scenarios,
            completionRate=round(completion_rate, 1),
        )

    async def get_all_sessions_summary(self) -> List[Dict[str, Any]]:
        summaries = []
        for session_id, session in self._sessions.items():
            progress_list = await self.get_progress(session_id)
            summaries.append({
                "sessionId": session_id,
                "userName": session.user_name,
                "createdAt": session.created_at.isoformat() if session.created_at else None,
                "completedCount": len(progress_list),
                "totalScenarios": 12,
                "completionRate": round(len(progress_list) / 12 * 100, 1),
            })
        return summaries


# 싱글톤 인스턴스
_repository_instance = None


@lru_cache
def get_onboarding_repository():
    """온보딩 저장소 인스턴스 반환."""
    global _repository_instance
    if _repository_instance is not None:
        return _repository_instance

    client = _build_supabase_client()
    if client:
        LOGGER.info("Using Supabase for onboarding repository")
        _repository_instance = OnboardingRepository(client)
    else:
        LOGGER.info("Using in-memory fallback for onboarding repository")
        _repository_instance = InMemoryOnboardingRepository()

    return _repository_instance
