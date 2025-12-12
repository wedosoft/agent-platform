"""온보딩 진행도 관련 데이터 모델."""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class OnboardingSession(BaseModel):
    """온보딩 세션 모델."""

    id: Optional[int] = None
    session_id: str = Field(..., alias="sessionId")
    user_name: str = Field(..., alias="userName")
    created_at: Optional[datetime] = Field(None, alias="createdAt")
    updated_at: Optional[datetime] = Field(None, alias="updatedAt")

    class Config:
        populate_by_name = True


class OnboardingProgress(BaseModel):
    """온보딩 진행도 모델."""

    id: Optional[int] = None
    session_id: str = Field(..., alias="sessionId")
    scenario_id: str = Field(..., alias="scenarioId")
    choice_id: str = Field(..., alias="choiceId")
    feedback_rating: Optional[int] = Field(None, alias="feedbackRating")
    completed_at: Optional[datetime] = Field(None, alias="completedAt")

    class Config:
        populate_by_name = True


class OnboardingProgressSummary(BaseModel):
    """온보딩 진행도 요약 응답 모델."""

    user_id: str = Field(..., alias="userId")
    user_name: str = Field(..., alias="userName")
    completed_scenarios: List[OnboardingProgress] = Field(default_factory=list, alias="completedScenarios")
    total_scenarios: int = Field(12, alias="totalScenarios")
    completion_rate: float = Field(0.0, alias="completionRate")

    class Config:
        populate_by_name = True


class KnowledgeArticle(BaseModel):
    """자료실 지식 문서 모델."""

    id: Optional[str] = None
    title: str
    author: str
    category: str
    raw_content: str = Field(..., alias="rawContent")
    structured_summary: Optional[str] = Field(None, alias="structuredSummary")
    created_at: Optional[datetime] = Field(None, alias="createdAt")
    updated_at: Optional[datetime] = Field(None, alias="updatedAt")

    class Config:
        populate_by_name = True
