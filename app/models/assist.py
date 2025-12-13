"""
AI Assistant 요청/응답 모델

FDK Custom App에서 사용하는 티켓 분석, 승인, 수정 API 모델 정의
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field
from pydantic.config import ConfigDict


# =============================================================================
# Request Models
# =============================================================================

class AnalyzeRequest(BaseModel):
    """티켓 분석 요청 모델"""
    model_config = ConfigDict(populate_by_name=True)

    ticket_id: str = Field(..., alias="ticketId")
    subject: Optional[str] = None
    description: Optional[str] = None
    priority: Optional[int] = None
    status: Optional[int] = None
    tags: Optional[List[str]] = None
    ticket_fields: Optional[List[Dict[str, Any]]] = Field(default=None, alias="ticketFields")
    stream_progress: bool = Field(default=True, alias="streamProgress")
    async_mode: bool = Field(default=False, alias="asyncMode")
    fields_only: bool = Field(default=False, alias="fieldsOnly")


class ApproveRequest(BaseModel):
    """제안 승인/거절 요청 모델"""
    model_config = ConfigDict(populate_by_name=True)

    ticket_id: str = Field(..., alias="ticketId")
    proposal_id: str = Field(..., alias="proposalId")
    action: str  # approve | reject
    final_response: Optional[str] = Field(default=None, alias="finalResponse")
    rejection_reason: Optional[str] = Field(default=None, alias="rejectionReason")
    agent_email: Optional[str] = Field(default=None, alias="agentEmail")


class RefineRequest(BaseModel):
    """제안 수정 요청 모델"""
    model_config = ConfigDict(populate_by_name=True)

    ticket_id: str = Field(..., alias="ticketId")
    proposal_id: str = Field(..., alias="proposalId")
    refinement_request: str = Field(..., alias="refinementRequest")
    agent_email: Optional[str] = Field(default=None, alias="agentEmail")


# =============================================================================
# Response Models
# =============================================================================

class FieldUpdate(BaseModel):
    """필드 업데이트 모델"""
    field: str
    old_value: Optional[Any] = Field(default=None, alias="oldValue")
    new_value: Any = Field(..., alias="newValue")


class SimilarCase(BaseModel):
    """유사 사례 모델"""
    model_config = ConfigDict(populate_by_name=True)

    ticket_id: str = Field(..., alias="ticketId")
    subject: str
    similarity_score: float = Field(..., alias="similarityScore")
    resolution: Optional[str] = None
    url: Optional[str] = None


class KBReference(BaseModel):
    """KB 참조 모델"""
    model_config = ConfigDict(populate_by_name=True)

    article_id: str = Field(..., alias="articleId")
    title: str
    relevance_score: float = Field(..., alias="relevanceScore")
    excerpt: Optional[str] = None
    url: Optional[str] = None


class FieldProposal(BaseModel):
    """개별 필드 제안 모델"""
    model_config = ConfigDict(populate_by_name=True)

    field_name: str = Field(..., alias="fieldName")
    field_label: str = Field(..., alias="fieldLabel")
    proposed_value: Any = Field(..., alias="proposedValue")
    reason: str


class Proposal(BaseModel):
    """AI 제안 모델"""
    model_config = ConfigDict(populate_by_name=True)

    id: str
    tenant_id: str = Field(..., alias="tenantId")
    ticket_id: str = Field(..., alias="ticketId")
    proposal_version: int = Field(default=1, alias="proposalVersion")

    # 분석 결과
    summary: Optional[str] = None
    intent: Optional[str] = None
    sentiment: Optional[str] = None

    # 제안 내용
    draft_response: Optional[str] = Field(default=None, alias="draftResponse")
    field_updates: Optional[Dict[str, Any]] = Field(default=None, alias="fieldUpdates")
    field_proposals: Optional[List[FieldProposal]] = Field(default=None, alias="fieldProposals")
    reasoning: Optional[str] = None

    # 메타데이터
    confidence: Optional[str] = None  # high | medium | low
    mode: Optional[str] = None  # synthesis | direct | fallback

    # 참조
    similar_cases: Optional[List[SimilarCase]] = Field(default=None, alias="similarCases")
    kb_references: Optional[List[KBReference]] = Field(default=None, alias="kbReferences")

    # 상태
    status: str = "draft"  # draft | approved | rejected | superseded
    approved_by: Optional[str] = Field(default=None, alias="approvedBy")
    approved_at: Optional[datetime] = Field(default=None, alias="approvedAt")
    rejection_reason: Optional[str] = Field(default=None, alias="rejectionReason")

    # 성능
    analysis_time_ms: Optional[int] = Field(default=None, alias="analysisTimeMs")
    token_count: Optional[int] = Field(default=None, alias="tokenCount")
    created_at: Optional[datetime] = Field(default=None, alias="createdAt")


class AnalyzeResponse(BaseModel):
    """분석 완료 응답 (non-streaming)"""
    model_config = ConfigDict(populate_by_name=True)

    proposal: Proposal


class ApproveResponse(BaseModel):
    """승인/거절 응답"""
    model_config = ConfigDict(populate_by_name=True)

    status: str
    field_updates: Optional[Dict[str, Any]] = Field(default=None, alias="fieldUpdates")
    final_response: Optional[str] = Field(default=None, alias="finalResponse")
    reason: Optional[str] = None  # 거절 시


class RefineResponse(BaseModel):
    """수정 응답"""
    model_config = ConfigDict(populate_by_name=True)

    proposal: Proposal
    version: int


# =============================================================================
# SSE Event Models
# =============================================================================

class SSEEvent(BaseModel):
    """SSE 이벤트 기본 모델"""
    type: str
    timestamp: Optional[float] = None


class RouterDecisionEvent(SSEEvent):
    """라우터 결정 이벤트"""
    type: str = "router_decision"
    decision: str  # retrieve_cases | propose_solution_direct
    reasoning: str
    embedding_enabled: bool = Field(..., alias="embeddingEnabled")


class RetrieverStartEvent(SSEEvent):
    """검색 시작 이벤트"""
    type: str = "retriever_start"
    mode: str = "embedding"


class RetrieverResultsEvent(SSEEvent):
    """검색 결과 이벤트"""
    type: str = "retriever_results"
    similar_cases_count: int = Field(..., alias="similarCasesCount")
    kb_articles_count: int = Field(..., alias="kbArticlesCount")
    total_results: int = Field(..., alias="totalResults")


class ResolutionStartEvent(SSEEvent):
    """솔루션 생성 시작 이벤트"""
    type: str = "resolution_start"


class ResolutionCompleteEvent(SSEEvent):
    """솔루션 생성 완료 이벤트"""
    type: str = "resolution_complete"
    proposal_id: str = Field(..., alias="proposalId")
    confidence: str
    mode: str
    analysis_time_ms: int = Field(..., alias="analysisTimeMs")


class HeartbeatEvent(SSEEvent):
    """하트비트 이벤트"""
    type: str = "heartbeat"


class ErrorEvent(SSEEvent):
    """에러 이벤트"""
    type: str = "error"
    message: str
    recoverable: bool = False
