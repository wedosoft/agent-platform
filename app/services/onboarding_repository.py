"""온보딩 진행도 저장소 - Supabase 연동."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from functools import lru_cache
from typing import Any, Dict, List, Optional

from supabase import Client, ClientOptions, create_client

from app.core.config import get_settings
from app.models.onboarding import (
    KnowledgeArticle,
    OnboardingProgress,
    OnboardingProgressSummary,
    OnboardingSession,
)

LOGGER = logging.getLogger(__name__)

# Supabase 테이블명
TABLE_SESSIONS = "onboarding_sessions"
TABLE_PROGRESS = "onboarding_progress"
TABLE_KNOWLEDGE_ARTICLES = "knowledge_articles"


class OnboardingRepositoryError(RuntimeError):
    """온보딩 저장소 에러."""
    pass


class OnboardingRepository:
    """온보딩 세션 및 진행도 저장소 (Supabase 기반)."""

    def __init__(self, client: Client) -> None:
        self.client = client
        # Backward-compatible alias: 일부 라우트/레거시 코드에서 repo.supabase를 참조함.
        self.supabase = client

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
        """세션 ID로 세션 조회."""
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

    async def get_session_by_user_name(self, user_name: str) -> Optional[OnboardingSession]:
        """사용자 이름으로 세션 조회 (중복 세션이 있으면 통합 후 반환)."""
        try:
            # 정규화된 이름으로 조회 (대소문자 구분 없이)
            normalized_name = user_name.strip()
            
            response = (
                self.client.table(TABLE_SESSIONS)
                .select("*")
                .ilike("user_name", normalized_name)
                .order("created_at", desc=True)
                .execute()
            )
            
            if not response.data:
                return None
            
            # 중복 세션이 있으면 첫 번째(가장 최근) 세션으로 통합
            if len(response.data) > 1:
                LOGGER.warning(f"Found {len(response.data)} duplicate sessions for user '{normalized_name}', consolidating...")
                await self._consolidate_sessions(response.data)
            
            row = response.data[0]
            return OnboardingSession(
                id=row.get("id"),
                sessionId=row["session_id"],
                userName=row["user_name"],
                createdAt=row.get("created_at"),
                updatedAt=row.get("updated_at"),
            )
        except Exception as e:
            LOGGER.error(f"Failed to get session by user_name: {e}")
            return None

    async def _consolidate_sessions(self, sessions: List[Dict[str, Any]]) -> None:
        """중복 세션을 첫 번째 세션으로 통합 (시나리오 진행률 + 커리큘럼 모듈 진행률 포함)."""
        if len(sessions) <= 1:
            return
        
        primary_session = sessions[0]
        primary_session_id = primary_session["session_id"]
        duplicate_session_ids = [s["session_id"] for s in sessions[1:]]
        
        LOGGER.info(f"Consolidating sessions: keeping {primary_session_id}, merging from {duplicate_session_ids}")
        
        try:
            for dup_session_id in duplicate_session_ids:
                # 1. 시나리오 진행률 통합 (onboarding_progress)
                dup_progress = (
                    self.client.table(TABLE_PROGRESS)
                    .select("*")
                    .eq("session_id", dup_session_id)
                    .execute()
                )
                
                for row in dup_progress.data or []:
                    scenario_id = row["scenario_id"]
                    existing = (
                        self.client.table(TABLE_PROGRESS)
                        .select("id")
                        .eq("session_id", primary_session_id)
                        .eq("scenario_id", scenario_id)
                        .execute()
                    )
                    if not existing.data:
                        self.client.table(TABLE_PROGRESS).update(
                            {"session_id": primary_session_id}
                        ).eq("id", row["id"]).execute()
                        LOGGER.debug(f"Moved scenario progress {scenario_id} to {primary_session_id}")
                    else:
                        self.client.table(TABLE_PROGRESS).delete().eq("id", row["id"]).execute()
                
                # 2. 커리큘럼 모듈 진행률 통합 (module_progress - onboarding 스키마)
                try:
                    # onboarding 스키마의 module_progress 테이블 접근
                    dup_module_progress = (
                        self.client.table("module_progress")
                        .select("*")
                        .eq("session_id", dup_session_id)
                        .execute()
                    )
                    
                    for row in dup_module_progress.data or []:
                        module_id = row["module_id"]
                        existing = (
                            self.client.table("module_progress")
                            .select("id")
                            .eq("session_id", primary_session_id)
                            .eq("module_id", module_id)
                            .execute()
                        )
                        if not existing.data:
                            # 진행률 이동
                            self.client.table("module_progress").update(
                                {"session_id": primary_session_id}
                            ).eq("id", row["id"]).execute()
                            LOGGER.debug(f"Moved module progress {module_id} to {primary_session_id}")
                        else:
                            # 기존 진행률이 있으면 더 높은 상태 유지 (completed > learning > not_started)
                            existing_row = (
                                self.client.table("module_progress")
                                .select("*")
                                .eq("session_id", primary_session_id)
                                .eq("module_id", module_id)
                                .execute()
                            )
                            if existing_row.data:
                                existing_status = existing_row.data[0].get("status", "not_started")
                                dup_status = row.get("status", "not_started")
                                status_priority = {"not_started": 0, "learning": 1, "completed": 2}
                                
                                if status_priority.get(dup_status, 0) > status_priority.get(existing_status, 0):
                                    # 중복 세션의 진행률이 더 높으면 업데이트
                                    self.client.table("module_progress").update({
                                        "status": dup_status,
                                        "quiz_score": row.get("quiz_score"),
                                        "quiz_passed_at": row.get("quiz_passed_at"),
                                        "learning_completed_at": row.get("learning_completed_at"),
                                    }).eq("id", existing_row.data[0]["id"]).execute()
                                    LOGGER.debug(f"Updated module progress {module_id} to {dup_status}")
                            
                            # 중복 진행률 삭제
                            self.client.table("module_progress").delete().eq("id", row["id"]).execute()
                except Exception as module_err:
                    LOGGER.warning(f"Failed to consolidate module progress: {module_err}")
                
                # 3. 중복 세션 삭제
                self.client.table(TABLE_SESSIONS).delete().eq("session_id", dup_session_id).execute()
                LOGGER.info(f"Deleted duplicate session: {dup_session_id}")
                
        except Exception as e:
            LOGGER.error(f"Failed to consolidate sessions: {e}")

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
        """모든 사용자의 진행도 요약 (관리자용) - 사용자 단위로 통합."""
        try:
            # 모든 세션 조회
            sessions_response = (
                self.client.table(TABLE_SESSIONS)
                .select("session_id, user_name, created_at")
                .order("created_at", desc=True)
                .execute()
            )

            # 사용자별로 세션 그룹화 (중복 세션 자동 통합)
            user_sessions: Dict[str, List[Dict[str, Any]]] = {}
            for session_row in (sessions_response.data or []):
                user_name = session_row["user_name"].strip().lower()  # 정규화
                if user_name not in user_sessions:
                    user_sessions[user_name] = []
                user_sessions[user_name].append(session_row)
            
            summaries = []
            for user_name, sessions in user_sessions.items():
                # 중복 세션이 있으면 통합
                if len(sessions) > 1:
                    LOGGER.info(f"Found {len(sessions)} sessions for user '{user_name}', consolidating...")
                    await self._consolidate_sessions(sessions)
                    # 통합 후 첫 번째 세션 사용
                
                primary_session = sessions[0]
                session_id = primary_session["session_id"]
                progress_list = await self.get_progress(session_id)

                summaries.append({
                    "sessionId": session_id,
                    "userName": primary_session["user_name"],  # 원본 이름 유지
                    "createdAt": primary_session["created_at"],
                    "completedCount": len(progress_list),
                    "totalScenarios": 12,
                    "completionRate": round(len(progress_list) / 12 * 100, 1),
                })

            return summaries
        except Exception as e:
            LOGGER.error(f"Failed to get all sessions summary: {e}")
            return []

    # ============================================
    # 자료실 (Knowledge Articles) 관리
    # ============================================

    async def create_knowledge_article(
        self,
        title: str,
        author: str,
        category: str,
        raw_content: str,
        structured_summary: Optional[str] = None,
    ) -> KnowledgeArticle:
        """자료실 문서 생성."""
        now = datetime.now(timezone.utc).isoformat()
        data = {
            "title": title,
            "author": author,
            "category": category,
            "raw_content": raw_content,
            "structured_summary": structured_summary,
            "created_at": now,
            "updated_at": now,
        }

        try:
            response = self.client.table(TABLE_KNOWLEDGE_ARTICLES).insert(data).execute()
            if response.data:
                row = response.data[0]
                return KnowledgeArticle(
                    id=row["id"],
                    title=row["title"],
                    author=row["author"],
                    category=row["category"],
                    rawContent=row["raw_content"],
                    structuredSummary=row.get("structured_summary"),
                    createdAt=row.get("created_at"),
                    updatedAt=row.get("updated_at"),
                )
            raise OnboardingRepositoryError("Failed to create knowledge article")
        except Exception as e:
            LOGGER.error(f"Failed to create knowledge article: {e}")
            raise OnboardingRepositoryError(str(e)) from e

    async def get_knowledge_articles(
        self, category: Optional[str] = None
    ) -> List[KnowledgeArticle]:
        """자료실 문서 목록 조회 (카테고리별 필터링 가능)."""
        try:
            query = self.client.table(TABLE_KNOWLEDGE_ARTICLES).select("*")

            if category:
                query = query.eq("category", category)

            response = query.order("created_at", desc=True).execute()

            return [
                KnowledgeArticle(
                    id=row["id"],
                    title=row["title"],
                    author=row["author"],
                    category=row["category"],
                    rawContent=row["raw_content"],
                    structuredSummary=row.get("structured_summary"),
                    createdAt=row.get("created_at"),
                    updatedAt=row.get("updated_at"),
                )
                for row in (response.data or [])
            ]
        except Exception as e:
            LOGGER.error(f"Failed to get knowledge articles: {e}")
            return []

    async def get_knowledge_article(self, article_id: str) -> Optional[KnowledgeArticle]:
        """자료실 문서 단건 조회."""
        try:
            response = (
                self.client.table(TABLE_KNOWLEDGE_ARTICLES)
                .select("*")
                .eq("id", article_id)
                .limit(1)
                .execute()
            )
            if response.data:
                row = response.data[0]
                return KnowledgeArticle(
                    id=row["id"],
                    title=row["title"],
                    author=row["author"],
                    category=row["category"],
                    rawContent=row["raw_content"],
                    structuredSummary=row.get("structured_summary"),
                    createdAt=row.get("created_at"),
                    updatedAt=row.get("updated_at"),
                )
            return None
        except Exception as e:
            LOGGER.error(f"Failed to get knowledge article: {e}")
            return None

    async def update_knowledge_article(
        self,
        article_id: str,
        title: Optional[str] = None,
        author: Optional[str] = None,
        category: Optional[str] = None,
        raw_content: Optional[str] = None,
        structured_summary: Optional[str] = None,
    ) -> Optional[KnowledgeArticle]:
        """자료실 문서 수정."""
        data = {}
        if title is not None:
            data["title"] = title
        if author is not None:
            data["author"] = author
        if category is not None:
            data["category"] = category
        if raw_content is not None:
            data["raw_content"] = raw_content
        if structured_summary is not None:
            data["structured_summary"] = structured_summary

        if not data:
            return await self.get_knowledge_article(article_id)

        data["updated_at"] = datetime.now(timezone.utc).isoformat()

        try:
            response = (
                self.client.table(TABLE_KNOWLEDGE_ARTICLES)
                .update(data)
                .eq("id", article_id)
                .execute()
            )
            if response.data:
                row = response.data[0]
                return KnowledgeArticle(
                    id=row["id"],
                    title=row["title"],
                    author=row["author"],
                    category=row["category"],
                    rawContent=row["raw_content"],
                    structuredSummary=row.get("structured_summary"),
                    createdAt=row.get("created_at"),
                    updatedAt=row.get("updated_at"),
                )
            return None
        except Exception as e:
            LOGGER.error(f"Failed to update knowledge article: {e}")
            raise OnboardingRepositoryError(str(e)) from e

    async def delete_knowledge_article(self, article_id: str) -> bool:
        """자료실 문서 삭제."""
        try:
            response = (
                self.client.table(TABLE_KNOWLEDGE_ARTICLES)
                .delete()
                .eq("id", article_id)
                .execute()
            )
            return len(response.data or []) > 0
        except Exception as e:
            LOGGER.error(f"Failed to delete knowledge article: {e}")
            raise OnboardingRepositoryError(str(e)) from e


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
        self._knowledge: Dict[str, KnowledgeArticle] = {}

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

    # ============================================
    # 자료실 (Knowledge Articles) 관리 - 인메모리
    # ============================================

    async def create_knowledge_article(
        self,
        title: str,
        author: str,
        category: str,
        raw_content: str,
        structured_summary: Optional[str] = None,
    ) -> KnowledgeArticle:
        import uuid

        now = datetime.now(timezone.utc)
        article_id = str(uuid.uuid4())
        article = KnowledgeArticle(
            id=article_id,
            title=title,
            author=author,
            category=category,
            rawContent=raw_content,
            structuredSummary=structured_summary,
            createdAt=now,
            updatedAt=now,
        )
        self._knowledge[article_id] = article
        return article

    async def get_knowledge_articles(self, category: Optional[str] = None) -> List[KnowledgeArticle]:
        articles = list(self._knowledge.values())
        if category:
            articles = [a for a in articles if a.category == category]
        # 최신순 정렬
        return sorted(
            articles,
            key=lambda a: a.created_at or datetime.min.replace(tzinfo=timezone.utc),
            reverse=True,
        )

    async def get_knowledge_article(self, article_id: str) -> Optional[KnowledgeArticle]:
        return self._knowledge.get(article_id)

    async def update_knowledge_article(
        self,
        article_id: str,
        title: Optional[str] = None,
        author: Optional[str] = None,
        category: Optional[str] = None,
        raw_content: Optional[str] = None,
        structured_summary: Optional[str] = None,
    ) -> Optional[KnowledgeArticle]:
        article = self._knowledge.get(article_id)
        if not article:
            return None

        update_data = {}
        if title is not None:
            update_data["title"] = title
        if author is not None:
            update_data["author"] = author
        if category is not None:
            update_data["category"] = category
        if raw_content is not None:
            update_data["rawContent"] = raw_content
        if structured_summary is not None:
            update_data["structuredSummary"] = structured_summary

        update_data["updatedAt"] = datetime.now(timezone.utc)
        updated_article = article.model_copy(update=update_data)
        self._knowledge[article_id] = updated_article
        return updated_article

    async def delete_knowledge_article(self, article_id: str) -> bool:
        if article_id in self._knowledge:
            del self._knowledge[article_id]
            return True
        return False


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
        # 인메모리 폴백은 개발/테스트 전용. 운영에서는 즉시 실패시켜 문제를 조기에 알린다.
        LOGGER.error("Supabase 설정이 없어 온보딩 자료실을 영구 저장할 수 없습니다. 환경변수를 설정하세요.")
        raise OnboardingRepositoryError(
            "Supabase 설정(supabase_common_url, supabase_common_service_role_key)이 필요합니다."
        )

    return _repository_instance
