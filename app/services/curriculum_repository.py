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
TABLE_PROGRESS = "user_module_progress"

PASSING_SCORE = 80  # 통과 기준 점수


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
                .eq("product", product)
                .order("display_order")
            )
            
            if active_only:
                query = query.eq("is_active", True)
            
            response = query.execute()
            
            modules = []
            for row in response.data or []:
                modules.append(CurriculumModule(
                    id=row["id"],
                    product=row["product"],
                    nameKo=row["name_ko"],
                    nameEn=row.get("name_en"),
                    slug=row["slug"],
                    description=row.get("description"),
                    icon=row.get("icon"),
                    estimatedMinutes=row.get("estimated_minutes", 30),
                    displayOrder=row.get("display_order", 0),
                    isActive=row.get("is_active", True),
                    kbCategorySlug=row.get("kb_category_slug"),
                    prerequisites=row.get("prerequisites"),
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
                    product=row["product"],
                    nameKo=row["name_ko"],
                    nameEn=row.get("name_en"),
                    slug=row["slug"],
                    description=row.get("description"),
                    icon=row.get("icon"),
                    estimatedMinutes=row.get("estimated_minutes", 30),
                    displayOrder=row.get("display_order", 0),
                    isActive=row.get("is_active", True),
                    kbCategorySlug=row.get("kb_category_slug"),
                    prerequisites=row.get("prerequisites"),
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
                .eq("product", product)
                .eq("slug", slug)
                .limit(1)
                .execute()
            )
            
            if response.data:
                row = response.data[0]
                return CurriculumModule(
                    id=row["id"],
                    product=row["product"],
                    nameKo=row["name_ko"],
                    nameEn=row.get("name_en"),
                    slug=row["slug"],
                    description=row.get("description"),
                    icon=row.get("icon"),
                    estimatedMinutes=row.get("estimated_minutes", 30),
                    displayOrder=row.get("display_order", 0),
                    isActive=row.get("is_active", True),
                    kbCategorySlug=row.get("kb_category_slug"),
                    prerequisites=row.get("prerequisites"),
                    createdAt=row.get("created_at"),
                )
            return None
        except Exception as e:
            LOGGER.error(f"Failed to get module by slug: {e}")
            return None

    # ============================================
    # 퀴즈 문제 조회
    # ============================================

    async def get_questions(
        self,
        module_id: UUID,
        difficulty: str,
        active_only: bool = True,
    ) -> List[QuizQuestion]:
        """모듈별 퀴즈 문제 조회 (정답 제외)."""
        try:
            query = (
                self.client.table(TABLE_QUESTIONS)
                .select("id, module_id, difficulty, question_order, question, context, choices, kb_document_id, reference_url")
                .eq("module_id", str(module_id))
                .eq("difficulty", difficulty)
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
                    difficulty=row["difficulty"],
                    questionOrder=row.get("question_order", 0),
                    question=row["question"],
                    context=row.get("context"),
                    choices=choices,
                    kbDocumentId=row.get("kb_document_id"),
                    referenceUrl=row.get("reference_url"),
                ))
            return questions
        except Exception as e:
            LOGGER.error(f"Failed to get quiz questions: {e}")
            raise CurriculumRepositoryError(str(e)) from e

    async def get_questions_with_answers(
        self,
        module_id: UUID,
        difficulty: str,
    ) -> List[QuizQuestionWithAnswer]:
        """모듈별 퀴즈 문제 조회 (정답 포함 - 채점용)."""
        try:
            response = (
                self.client.table(TABLE_QUESTIONS)
                .select("*")
                .eq("module_id", str(module_id))
                .eq("difficulty", difficulty)
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
                    difficulty=row["difficulty"],
                    questionOrder=row.get("question_order", 0),
                    question=row["question"],
                    context=row.get("context"),
                    choices=choices,
                    correctChoiceId=row["correct_choice_id"],
                    explanation=row.get("explanation"),
                    kbDocumentId=row.get("kb_document_id"),
                    referenceUrl=row.get("reference_url"),
                ))
            return questions
        except Exception as e:
            LOGGER.error(f"Failed to get quiz questions with answers: {e}")
            raise CurriculumRepositoryError(str(e)) from e

    # ============================================
    # 퀴즈 제출 및 채점
    # ============================================

    async def submit_quiz(
        self,
        session_id: str,
        module_id: UUID,
        difficulty: str,
        answers: List[QuizAnswer],
        started_at: Optional[datetime] = None,
    ) -> QuizSubmitResponse:
        """퀴즈 제출 및 채점."""
        try:
            # 1. 정답 조회
            questions = await self.get_questions_with_answers(module_id, difficulty)
            if not questions:
                raise CurriculumRepositoryError("No questions found for this module and difficulty")
            
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
            is_passed = score >= PASSING_SCORE
            
            # 3. 시도 기록 저장
            now = datetime.now(timezone.utc)
            duration_seconds = None
            if started_at:
                duration_seconds = int((now - started_at).total_seconds())
            
            attempt_data = {
                "session_id": session_id,
                "module_id": str(module_id),
                "difficulty": difficulty,
                "score": score,
                "total_questions": total_questions,
                "correct_count": correct_count,
                "is_passed": is_passed,
                "answers": [r.model_dump(by_alias=True) for r in results],
                "started_at": started_at.isoformat() if started_at else None,
                "completed_at": now.isoformat(),
                "duration_seconds": duration_seconds,
            }
            
            self.client.table(TABLE_ATTEMPTS).insert(attempt_data).execute()
            
            # 4. 진도 업데이트
            await self._update_progress_after_quiz(
                session_id=session_id,
                module_id=module_id,
                difficulty=difficulty,
                score=score,
                is_passed=is_passed,
            )
            
            return QuizSubmitResponse(
                moduleId=module_id,
                difficulty=difficulty,
                score=score,
                totalQuestions=total_questions,
                correctCount=correct_count,
                isPassed=is_passed,
                passingScore=PASSING_SCORE,
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
        difficulty: str,
        score: int,
        is_passed: bool,
    ) -> None:
        """퀴즈 제출 후 진도 업데이트."""
        try:
            # 기존 진도 조회
            progress = await self.get_progress(session_id, module_id)
            
            now = datetime.now(timezone.utc).isoformat()
            
            if progress:
                # 업데이트
                update_data = {"updated_at": now}
                
                if difficulty == "basic":
                    update_data["basic_quiz_score"] = score
                    update_data["basic_quiz_passed"] = is_passed
                    update_data["basic_quiz_attempts"] = (progress.basic_quiz_attempts or 0) + 1
                else:  # advanced
                    update_data["advanced_quiz_score"] = score
                    update_data["advanced_quiz_passed"] = is_passed
                    update_data["advanced_quiz_attempts"] = (progress.advanced_quiz_attempts or 0) + 1
                
                # 기초+심화 모두 통과하면 완료
                basic_passed = update_data.get("basic_quiz_passed", progress.basic_quiz_passed)
                advanced_passed = update_data.get("advanced_quiz_passed", progress.advanced_quiz_passed)
                
                if basic_passed and advanced_passed:
                    update_data["status"] = "completed"
                    update_data["completed_at"] = now
                elif is_passed:
                    update_data["status"] = "quiz_ready"  # 다음 난이도 준비
                
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
                    "status": "quiz_ready" if is_passed else "learning",
                    "created_at": now,
                    "updated_at": now,
                }
                
                if difficulty == "basic":
                    insert_data["basic_quiz_score"] = score
                    insert_data["basic_quiz_passed"] = is_passed
                    insert_data["basic_quiz_attempts"] = 1
                else:
                    insert_data["advanced_quiz_score"] = score
                    insert_data["advanced_quiz_passed"] = is_passed
                    insert_data["advanced_quiz_attempts"] = 1
                
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
                    basicQuizScore=row.get("basic_quiz_score"),
                    basicQuizPassed=row.get("basic_quiz_passed", False),
                    basicQuizAttempts=row.get("basic_quiz_attempts", 0),
                    advancedQuizScore=row.get("advanced_quiz_score"),
                    advancedQuizPassed=row.get("advanced_quiz_passed", False),
                    advancedQuizAttempts=row.get("advanced_quiz_attempts", 0),
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
                    basicQuizScore=row.get("basic_quiz_score"),
                    basicQuizPassed=row.get("basic_quiz_passed", False),
                    basicQuizAttempts=row.get("basic_quiz_attempts", 0),
                    advancedQuizScore=row.get("advanced_quiz_score"),
                    advancedQuizPassed=row.get("advanced_quiz_passed", False),
                    advancedQuizAttempts=row.get("advanced_quiz_attempts", 0),
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
                    if not status:
                        update_data["status"] = "quiz_ready"
                
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
                    insert_data["status"] = "quiz_ready"
                
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
        """모듈 목록과 진도 통합 조회."""
        try:
            # 모듈 목록
            modules = await self.get_modules(product=product)
            
            # 진도 조회
            progress_map = await self.get_all_progress(session_id)
            
            # 선행 조건 확인을 위한 모듈 ID -> 모듈 매핑
            module_map = {str(m.id): m for m in modules}
            
            result = []
            for module in modules:
                module_id_str = str(module.id)
                progress = progress_map.get(module_id_str)
                
                # 선행 조건 확인
                is_unlocked = True
                if module.prerequisites:
                    for prereq_id in module.prerequisites:
                        prereq_progress = progress_map.get(str(prereq_id))
                        if not prereq_progress or prereq_progress.status != "completed":
                            is_unlocked = False
                            break
                
                result.append(CurriculumModuleResponse(
                    id=module.id,
                    product=module.product,
                    nameKo=module.name_ko,
                    nameEn=module.name_en,
                    slug=module.slug,
                    description=module.description,
                    icon=module.icon,
                    estimatedMinutes=module.estimated_minutes,
                    displayOrder=module.display_order,
                    isUnlocked=is_unlocked,
                    status=progress.status if progress else "not_started",
                    basicQuizPassed=progress.basic_quiz_passed if progress else False,
                    advancedQuizPassed=progress.advanced_quiz_passed if progress else False,
                    basicQuizScore=progress.basic_quiz_score if progress else None,
                    advancedQuizScore=progress.advanced_quiz_score if progress else None,
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
