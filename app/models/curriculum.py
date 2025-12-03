"""커리큘럼 및 퀴즈 관련 데이터 모델."""

from datetime import datetime
from typing import List, Optional, Dict, Any
from uuid import UUID

from pydantic import BaseModel, Field


# ============================================
# Curriculum Module (학습 모듈)
# ============================================

class CurriculumModule(BaseModel):
    """커리큘럼 모듈 모델."""

    id: UUID
    product: str = "freshservice"
    name_ko: str = Field(..., alias="nameKo")
    name_en: Optional[str] = Field(None, alias="nameEn")
    slug: str
    description: Optional[str] = None
    icon: Optional[str] = None
    estimated_minutes: int = Field(30, alias="estimatedMinutes")
    display_order: int = Field(0, alias="displayOrder")
    is_active: bool = Field(True, alias="isActive")
    kb_category_slug: Optional[str] = Field(None, alias="kbCategorySlug")
    prerequisites: Optional[List[UUID]] = None
    created_at: Optional[datetime] = Field(None, alias="createdAt")

    class Config:
        populate_by_name = True
        from_attributes = True


class CurriculumModuleResponse(BaseModel):
    """커리큘럼 모듈 응답 (진도 포함)."""

    id: UUID
    product: str
    name_ko: str = Field(..., alias="nameKo")
    name_en: Optional[str] = Field(None, alias="nameEn")
    slug: str
    description: Optional[str] = None
    icon: Optional[str] = None
    estimated_minutes: int = Field(alias="estimatedMinutes")
    display_order: int = Field(alias="displayOrder")
    
    # 진도 정보
    is_unlocked: bool = Field(True, alias="isUnlocked")
    status: str = "not_started"  # not_started, learning, quiz_ready, completed
    basic_quiz_passed: bool = Field(False, alias="basicQuizPassed")
    advanced_quiz_passed: bool = Field(False, alias="advancedQuizPassed")
    basic_quiz_score: Optional[int] = Field(None, alias="basicQuizScore")
    advanced_quiz_score: Optional[int] = Field(None, alias="advancedQuizScore")

    class Config:
        populate_by_name = True


# ============================================
# Quiz Question (퀴즈 문제)
# ============================================

class QuizChoice(BaseModel):
    """퀴즈 선택지."""

    id: str
    text: str


class QuizQuestion(BaseModel):
    """퀴즈 문제 모델."""

    id: UUID
    module_id: UUID = Field(..., alias="moduleId")
    difficulty: str  # basic, advanced
    question_order: int = Field(0, alias="questionOrder")
    question: str
    context: Optional[str] = None
    choices: List[QuizChoice]
    # 정답은 클라이언트에 보내지 않음
    kb_document_id: Optional[UUID] = Field(None, alias="kbDocumentId")
    reference_url: Optional[str] = Field(None, alias="referenceUrl")

    class Config:
        populate_by_name = True
        from_attributes = True


class QuizQuestionWithAnswer(QuizQuestion):
    """퀴즈 문제 (정답 포함 - 내부용)."""

    correct_choice_id: str = Field(..., alias="correctChoiceId")
    explanation: Optional[str] = None


# ============================================
# Quiz Submit (퀴즈 제출)
# ============================================

class QuizAnswer(BaseModel):
    """퀴즈 답변."""

    question_id: UUID = Field(..., alias="questionId")
    choice_id: str = Field(..., alias="choiceId")


class QuizSubmitRequest(BaseModel):
    """퀴즈 제출 요청."""

    session_id: str = Field(..., alias="sessionId")
    module_id: UUID = Field(..., alias="moduleId")
    difficulty: str  # basic, advanced
    answers: List[QuizAnswer]
    started_at: Optional[datetime] = Field(None, alias="startedAt")

    class Config:
        populate_by_name = True


class QuizAnswerResult(BaseModel):
    """개별 답변 결과."""

    question_id: UUID = Field(..., alias="questionId")
    choice_id: str = Field(..., alias="choiceId")
    is_correct: bool = Field(..., alias="isCorrect")
    correct_choice_id: str = Field(..., alias="correctChoiceId")
    explanation: Optional[str] = None


class QuizSubmitResponse(BaseModel):
    """퀴즈 제출 응답."""

    module_id: UUID = Field(..., alias="moduleId")
    difficulty: str
    score: int
    total_questions: int = Field(..., alias="totalQuestions")
    correct_count: int = Field(..., alias="correctCount")
    is_passed: bool = Field(..., alias="isPassed")
    passing_score: int = Field(80, alias="passingScore")
    answers: List[QuizAnswerResult]
    duration_seconds: Optional[int] = Field(None, alias="durationSeconds")

    class Config:
        populate_by_name = True


# ============================================
# Module Progress (모듈 진도)
# ============================================

class ModuleProgress(BaseModel):
    """모듈 진도 모델."""

    id: Optional[UUID] = None
    session_id: str = Field(..., alias="sessionId")
    module_id: UUID = Field(..., alias="moduleId")
    status: str = "not_started"  # not_started, learning, quiz_ready, completed
    
    learning_started_at: Optional[datetime] = Field(None, alias="learningStartedAt")
    learning_completed_at: Optional[datetime] = Field(None, alias="learningCompletedAt")
    
    basic_quiz_score: Optional[int] = Field(None, alias="basicQuizScore")
    basic_quiz_passed: bool = Field(False, alias="basicQuizPassed")
    basic_quiz_attempts: int = Field(0, alias="basicQuizAttempts")
    
    advanced_quiz_score: Optional[int] = Field(None, alias="advancedQuizScore")
    advanced_quiz_passed: bool = Field(False, alias="advancedQuizPassed")
    advanced_quiz_attempts: int = Field(0, alias="advancedQuizAttempts")
    
    completed_at: Optional[datetime] = Field(None, alias="completedAt")

    class Config:
        populate_by_name = True
        from_attributes = True


class UpdateProgressRequest(BaseModel):
    """진도 업데이트 요청."""

    session_id: str = Field(..., alias="sessionId")
    status: Optional[str] = None  # learning, quiz_ready
    learning_completed: bool = Field(False, alias="learningCompleted")

    class Config:
        populate_by_name = True


class ProgressSummary(BaseModel):
    """전체 진도 요약."""

    session_id: str = Field(..., alias="sessionId")
    total_modules: int = Field(..., alias="totalModules")
    completed_modules: int = Field(..., alias="completedModules")
    in_progress_modules: int = Field(..., alias="inProgressModules")
    completion_rate: float = Field(..., alias="completionRate")
    modules: List[CurriculumModuleResponse]

    class Config:
        populate_by_name = True
