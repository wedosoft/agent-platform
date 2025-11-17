from __future__ import annotations

from datetime import datetime
from typing import Any, List, Optional

from pydantic import BaseModel, Field
from pydantic.config import ConfigDict


class SessionBase(BaseModel):
    model_config = ConfigDict(populate_by_name=True)


class SessionCreateResponse(SessionBase):
    session_id: str = Field(alias="sessionId")
    created_at: datetime = Field(alias="createdAt")
    ttl_minutes: int = Field(alias="ttlMinutes")


class SessionDetailResponse(SessionBase):
    session_id: str = Field(alias="sessionId")
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")
    question_history: List[Any] = Field(default_factory=list, alias="questionHistory")
    analyzer_responses: Optional[List[Any]] = Field(default=None, alias="analyzerResponses")
    clarification_state: Optional[Any] = Field(default=None, alias="clarificationState")
    extracted_filters: Optional[List[Any]] = Field(default=None, alias="extractedFilters")
    fallback_count: Optional[int] = Field(default=None, alias="fallbackCount")
    trace_ids: Optional[List[str]] = Field(default=None, alias="traceIds")
    known_context: Optional[dict] = Field(default=None, alias="knownContext")


class ChatRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    session_id: str = Field(..., alias="sessionId")
    query: str
    rag_store_name: Optional[str] = Field(default=None, alias="ragStoreName")
    sources: Optional[List[str]] = None
    common_product: Optional[str] = Field(default=None, alias="commonProduct")


class ChatResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="allow")

    text: str
    grounding_chunks: Optional[List[Any]] = Field(default=None, alias="groundingChunks")
    rag_store_name: Optional[str] = Field(default=None, alias="ragStoreName")
    sources: Optional[List[str]] = None
    filters: Optional[List[str]] = None
    filter_confidence: Optional[str] = Field(default=None, alias="filterConfidence")
    filter_warning: Optional[str] = Field(default=None, alias="filterWarning")
    clarification_needed: Optional[bool] = Field(default=None, alias="clarificationNeeded")
    clarification: Optional[dict] = None
    known_context: Optional[dict] = Field(default=None, alias="knownContext")
    freshdesk_search_plan: Optional[dict] = Field(default=None, alias="freshdeskSearchPlan")
    freshdesk_tickets: Optional[dict] = Field(default=None, alias="freshdeskTickets")
