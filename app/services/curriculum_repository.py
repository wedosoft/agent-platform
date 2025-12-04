"""커리큘럼 저장소 - Supabase 연동."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from functools import lru_cache
from typing import Any, Dict, List, Optional
from uuid import UUID

from supabase import Client, create_client

from app.core.config import get_settings
from app.models.curriculum import (
    CurriculumModule,
    CurriculumModuleResponse,
    ModuleProgress,
    QuizQuestion,
    QuizQuestionWithAnswer,
    QuizChoice,
    QuizAnswer,
    QuizAnswerResult,
    QuizSubmitResponse,
)

LOGGER = logging.getLogger(__name__)

# Supabase 테이블명
TABLE_MODULES = "curriculum_modules"
TABLE_QUESTIONS = "quiz_questions"
TABLE_ATTEMPTS = "quiz_attempts"
TABLE_PROGRESS = "module_progress"


class CurriculumRepositoryError(RuntimeError):
    """커리큘럼 저장소 에러."""
    pass


class CurriculumRepository:
    """커리큘럼 모듈, 퀴즈, 진도 저장소 (Supabase 기반)."""

    def __init__(self, client: Client) -> None:
        self.client = client

    # ============================================
    # 모듈 조회
    # ============================================

    async def get_modules(
        self,
        product: str = "freshservice",
        active_only: bool = True,
    ) -> List[CurriculumModule]:
        """제품별 커리큘럼 모듈 목록 조회."""
        try:
            query = (
                self.client.table(TABLE_MODULES)
                .select("*")
                .eq("target_product_id", product)
                .order("display_order")
            )
            
            if active_only:
                query = query.eq("is_active", True)
            
            response = query.execute()
            
            modules = []
            for row in response.data or []:
                modules.append(CurriculumModule(
                    id=row["id"],
                    targetProductId=row["target_product_id"],
                    targetProductType=row.get("target_product_type", "module"),
                    nameKo=row["name_ko"],
                    nameEn=row.get("name_en"),
                    slug=row["slug"],
                    description=row.get("description"),
                    icon=row.get("icon"),
                    estimatedMinutes=row.get("estimated_minutes", 30),
                    displayOrder=row.get("display_order", 0),
                    learningObjectives=row.get("learning_objectives"),
                    contentStrategy=row.get("content_strategy", "hybrid"),
                    isActive=row.get("is_active", True),
                    kbCategorySlug=row.get("kb_category_slug"),
                    createdAt=row.get("created_at"),
                ))
            return modules
        except Exception as e:
            LOGGER.error(f"Failed to get curriculum modules: {e}")
            raise CurriculumRepositoryError(str(e)) from e

    async def get_module_by_id(self, module_id: UUID) -> Optional[CurriculumModule]:
        """모듈 ID로 조회."""
        try:
            response = (
                self.client.table(TABLE_MODULES)
                .select("*")
                .eq("id", str(module_id))
                .limit(1)
                .execute()
            )
            
            if response.data:
                row = response.data[0]
                return CurriculumModule(
                    id=row["id"],
                    targetProductId=row["target_product_id"],
                    targetProductType=row.get("target_product_type", "module"),
                    nameKo=row["name_ko"],
                    nameEn=row.get("name_en"),
                    slug=row["slug"],
                    description=row.get("description"),
                    icon=row.get("icon"),
                    estimatedMinutes=row.get("estimated_minutes", 30),
                    displayOrder=row.get("display_order", 0),
                    learningObjectives=row.get("learning_objectives"),
                    contentStrategy=row.get("content_strategy", "hybrid"),
                    isActive=row.get("is_active", True),
                    kbCategorySlug=row.get("kb_category_slug"),
                    createdAt=row.get("created_at"),
                )
            return None
        except Exception as e:
            LOGGER.error(f"Failed to get module by id: {e}")
            return None

    async def get_module_by_slug(
        self,
        slug: str,
        product: str = "freshservice",
    ) -> Optional[CurriculumModule]:
        """슬러그로 모듈 조회."""
        try:
            response = (
                self.client.table(TABLE_MODULES)
                .select("*")
                .eq("target_product_id", product)
                .eq("slug", slug)
                .limit(1)
                .execute()
            )
            
            if response.data:
                row = response.data[0]
                return CurriculumModule(
                    id=row["id"],
                    targetProductId=row["target_product_id"],
                    targetProductType=row.get("target_product_type", "module"),
                    nameKo=row["name_ko"],
                    nameEn=row.get("name_en"),
                    slug=row["slug"],
                    description=row.get("description"),
                    icon=row.get("icon"),
                    estimatedMinutes=row.get("estimated_minutes", 30),
                    displayOrder=row.get("display_order", 0),
                    learningObjectives=row.get("learning_objectives"),
                    contentStrategy=row.get("content_strategy", "hybrid"),
                    isActive=row.get("is_active", True),
                    kbCategorySlug=row.get("kb_category_slug"),
                    createdAt=row.get("created_at"),
                )
            return None
        except Exception as e:
            LOGGER.error(f"Failed to get module by slug: {e}")
            return None

    # ============================================
    # 퀴즈 문제 조회 (자가 점검용 - 난이도 구분 없음)
    # ============================================

    async def get_questions(
        self,
        module_id: UUID,
        active_only: bool = True,
    ) -> List[QuizQuestion]:
        """모듈별 퀴즈 문제 조회 (정답 제외)."""
        try:
            query = (
                self.client.table(TABLE_QUESTIONS)
                .select("id, module_id, question_order, question, context, choices, related_doc_url")
                .eq("module_id", str(module_id))
                .order("question_order")
            )
            
            if active_only:
                query = query.eq("is_active", True)
            
            response = query.execute()
            
            questions = []
            for row in response.data or []:
                # choices JSONB를 QuizChoice 리스트로 변환
                choices = [QuizChoice(**c) for c in row.get("choices", [])]
                questions.append(QuizQuestion(
                    id=row["id"],
                    moduleId=row["module_id"],
                    questionOrder=row.get("question_order", 0),
                    question=row["question"],
                    context=row.get("context"),
                    choices=choices,
                    relatedDocUrl=row.get("related_doc_url"),
                ))
            return questions
        except Exception as e:
            LOGGER.error(f"Failed to get quiz questions: {e}")
            raise CurriculumRepositoryError(str(e)) from e

    async def get_questions_with_answers(
        self,
        module_id: UUID,
    ) -> List[QuizQuestionWithAnswer]:
        """모듈별 퀴즈 문제 조회 (정답 포함 - 채점용)."""
        try:
            response = (
                self.client.table(TABLE_QUESTIONS)
                .select("*")
                .eq("module_id", str(module_id))
                .eq("is_active", True)
                .order("question_order")
                .execute()
            )
            
            questions = []
            for row in response.data or []:
                choices = [QuizChoice(**c) for c in row.get("choices", [])]
                questions.append(QuizQuestionWithAnswer(
                    id=row["id"],
                    moduleId=row["module_id"],
                    questionOrder=row.get("question_order", 0),
                    question=row["question"],
                    context=row.get("context"),
                    choices=choices,
                    correctChoiceId=row["correct_choice_id"],
                    explanation=row.get("explanation"),
                    learningPoint=row.get("learning_point"),
                    relatedDocUrl=row.get("related_doc_url"),
                ))
            return questions
        except Exception as e:
            LOGGER.error(f"Failed to get quiz questions with answers: {e}")
            raise CurriculumRepositoryError(str(e)) from e

    # ============================================
    # 퀴즈 제출 및 채점 (자가 점검 - 통과/불통과 없음)
    # ============================================

    async def submit_quiz(
        self,
        session_id: str,
        module_id: UUID,
        answers: List[QuizAnswer],
        started_at: Optional[datetime] = None,
    ) -> QuizSubmitResponse:
        """퀴즈 제출 및 채점 (자가 점검용 - 통과/불통과 판정 없음)."""
        try:
            # 1. 정답 조회
            questions = await self.get_questions_with_answers(module_id)
            if not questions:
                raise CurriculumRepositoryError("No questions found for this module")
            
            # 문제 ID -> 정답 매핑
            answer_map: Dict[str, QuizQuestionWithAnswer] = {
                str(q.id): q for q in questions
            }
            
            # 2. 채점
            results: List[QuizAnswerResult] = []
            correct_count = 0
            
            for ans in answers:
                question = answer_map.get(str(ans.question_id))
                if not question:
                    continue
                
                is_correct = ans.choice_id == question.correct_choice_id
                if is_correct:
                    correct_count += 1
                
                results.append(QuizAnswerResult(
                    questionId=ans.question_id,
                    choiceId=ans.choice_id,
                    isCorrect=is_correct,
                    correctChoiceId=question.correct_choice_id,
                    explanation=question.explanation,
                ))
            
            total_questions = len(questions)
            score = int((correct_count / total_questions) * 100) if total_questions > 0 else 0
            
            # 3. 시도 기록 저장
            now = datetime.now(timezone.utc)
            actual_started_at = started_at or now
            duration_seconds = None
            if started_at:
                duration_seconds = int((now - started_at).total_seconds())
            
            attempt_data = {
                "session_id": session_id,
                "module_id": str(module_id),
                "difficulty": "basic",  # 새 스키마 필수 필드
                "score": score,
                "total_questions": total_questions,
                "correct_count": correct_count,
                "answers": [r.model_dump(by_alias=True, mode="json") for r in results],
                "started_at": actual_started_at.isoformat(),
                "completed_at": now.isoformat(),
                "duration_seconds": duration_seconds,
            }
            
            self.client.table(TABLE_ATTEMPTS).insert(attempt_data).execute()
            
            # 4. 진도 업데이트 (점수 기록)
            await self._update_progress_after_quiz(
                session_id=session_id,
                module_id=module_id,
                score=score,
            )
            
            return QuizSubmitResponse(
                moduleId=module_id,
                score=score,
                totalQuestions=total_questions,
                correctCount=correct_count,
                answers=results,
                durationSeconds=duration_seconds,
            )
        except CurriculumRepositoryError:
            raise
        except Exception as e:
            LOGGER.error(f"Failed to submit quiz: {e}")
            raise CurriculumRepositoryError(str(e)) from e

    async def _update_progress_after_quiz(
        self,
        session_id: str,
        module_id: UUID,
        score: int,
    ) -> None:
        """퀴즈 제출 후 진도 업데이트 (자가 점검 완료 시 completed로 변경)."""
        try:
            # 기존 진도 조회
            progress = await self.get_progress(session_id, module_id)
            
            now = datetime.now(timezone.utc).isoformat()
            
            if progress:
                # 업데이트 (점수 기록, 시도 횟수 증가, 완료 상태로 변경)
                update_data = {
                    "updated_at": now,
                    "status": "completed",  # 자가 점검 완료 시 completed
                    "completed_at": now,
                    "quiz_score": score,
                    "quiz_attempts": (progress.quiz_attempts or 0) + 1,
                }
                
                self.client.table(TABLE_PROGRESS).update(update_data).eq(
                    "session_id", session_id
                ).eq(
                    "module_id", str(module_id)
                ).execute()
            else:
                # 새로 생성 (학습 시작 없이 퀴즈만 본 경우)
                insert_data = {
                    "session_id": session_id,
                    "module_id": str(module_id),
                    "status": "completed",  # 자가 점검 완료 시 completed
                    "completed_at": now,
                    "quiz_score": score,
                    "quiz_attempts": 1,
                    "created_at": now,
                    "updated_at": now,
                }
                
                self.client.table(TABLE_PROGRESS).insert(insert_data).execute()
                
        except Exception as e:
            LOGGER.error(f"Failed to update progress after quiz: {e}")
            # 진도 업데이트 실패는 치명적이지 않으므로 예외를 던지지 않음

    # ============================================
    # 진도 관리
    # ============================================

    async def get_progress(
        self,
        session_id: str,
        module_id: UUID,
    ) -> Optional[ModuleProgress]:
        """세션별 모듈 진도 조회."""
        try:
            response = (
                self.client.table(TABLE_PROGRESS)
                .select("*")
                .eq("session_id", session_id)
                .eq("module_id", str(module_id))
                .limit(1)
                .execute()
            )
            
            if response.data:
                row = response.data[0]
                return ModuleProgress(
                    id=row.get("id"),
                    sessionId=row["session_id"],
                    moduleId=row["module_id"],
                    status=row.get("status", "not_started"),
                    learningStartedAt=row.get("learning_started_at"),
                    learningCompletedAt=row.get("learning_completed_at"),
                    quizScore=row.get("quiz_score"),
                    quizAttempts=row.get("quiz_attempts", 0),
                    learningTimeMinutes=row.get("learning_time_minutes", 0),
                    completedAt=row.get("completed_at"),
                )
            return None
        except Exception as e:
            LOGGER.error(f"Failed to get module progress: {e}")
            return None

    async def get_all_progress(
        self,
        session_id: str,
    ) -> Dict[str, ModuleProgress]:
        """세션의 전체 모듈 진도 조회."""
        try:
            response = (
                self.client.table(TABLE_PROGRESS)
                .select("*")
                .eq("session_id", session_id)
                .execute()
            )
            
            progress_map = {}
            for row in response.data or []:
                module_id = row["module_id"]
                progress_map[module_id] = ModuleProgress(
                    id=row.get("id"),
                    sessionId=row["session_id"],
                    moduleId=row["module_id"],
                    status=row.get("status", "not_started"),
                    learningStartedAt=row.get("learning_started_at"),
                    learningCompletedAt=row.get("learning_completed_at"),
                    quizScore=row.get("quiz_score"),
                    quizAttempts=row.get("quiz_attempts", 0),
                    learningTimeMinutes=row.get("learning_time_minutes", 0),
                    completedAt=row.get("completed_at"),
                )
            return progress_map
        except Exception as e:
            LOGGER.error(f"Failed to get all module progress: {e}")
            return {}

    async def update_progress(
        self,
        session_id: str,
        module_id: UUID,
        status: Optional[str] = None,
        learning_completed: bool = False,
    ) -> Optional[ModuleProgress]:
        """모듈 진도 업데이트."""
        try:
            now = datetime.now(timezone.utc).isoformat()
            
            # 기존 진도 조회
            progress = await self.get_progress(session_id, module_id)
            
            if progress:
                # 업데이트
                update_data = {"updated_at": now}
                
                if status:
                    update_data["status"] = status
                
                if learning_completed:
                    update_data["learning_completed_at"] = now
                
                self.client.table(TABLE_PROGRESS).update(update_data).eq(
                    "session_id", session_id
                ).eq(
                    "module_id", str(module_id)
                ).execute()
            else:
                # 새로 생성
                insert_data = {
                    "session_id": session_id,
                    "module_id": str(module_id),
                    "status": status or "learning",
                    "learning_started_at": now,
                    "created_at": now,
                    "updated_at": now,
                }
                
                if learning_completed:
                    insert_data["learning_completed_at"] = now
                
                self.client.table(TABLE_PROGRESS).insert(insert_data).execute()
            
            return await self.get_progress(session_id, module_id)
        except Exception as e:
            LOGGER.error(f"Failed to update module progress: {e}")
            raise CurriculumRepositoryError(str(e)) from e

    async def start_learning(
        self,
        session_id: str,
        module_id: UUID,
    ) -> Optional[ModuleProgress]:
        """학습 시작 기록."""
        return await self.update_progress(
            session_id=session_id,
            module_id=module_id,
            status="learning",
        )

    # ============================================
    # 모듈 + 진도 통합 조회
    # ============================================

    async def get_modules_with_progress(
        self,
        session_id: str,
        product: str = "freshservice",
    ) -> List[CurriculumModuleResponse]:
        """모듈 목록과 진도 통합 조회 (unlock 제거, 모든 모듈 접근 가능)."""
        try:
            # 모듈 목록
            modules = await self.get_modules(product=product)
            
            # 진도 조회
            progress_map = await self.get_all_progress(session_id)
            
            result = []
            for module in modules:
                module_id_str = str(module.id)
                progress = progress_map.get(module_id_str)
                
                result.append(CurriculumModuleResponse(
                    id=module.id,
                    targetProductId=module.target_product_id,
                    targetProductType=module.target_product_type,
                    nameKo=module.name_ko,
                    nameEn=module.name_en,
                    slug=module.slug,
                    description=module.description,
                    icon=module.icon,
                    estimatedMinutes=module.estimated_minutes,
                    displayOrder=module.display_order,
                    status=progress.status if progress else "not_started",
                    quizScore=progress.quiz_score if progress else None,
                    quizAttempts=progress.quiz_attempts if progress else 0,
                    learningTimeMinutes=progress.learning_time_minutes if progress else 0,
                ))
            
            return result
        except Exception as e:
            LOGGER.error(f"Failed to get modules with progress: {e}")
            raise CurriculumRepositoryError(str(e)) from e


# ============================================
# 싱글톤 인스턴스
# ============================================

_repository: Optional[CurriculumRepository] = None


def get_curriculum_repository() -> CurriculumRepository:
    """커리큘럼 저장소 싱글톤 인스턴스 반환."""
    global _repository
    
    if _repository is None:
        settings = get_settings()
        client = create_client(
            settings.supabase_common_url,
            settings.supabase_common_service_role_key,
        )
        _repository = CurriculumRepository(client)
    
    return _repository
