"""
Admin API 모델

테넌트 관리, 동기화 상태, 스토어 설정 관련 Pydantic 모델
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# =============================================================================
# 테넌트 설정 모델
# =============================================================================

class TenantConfig(BaseModel):
    """테넌트 설정"""

    tenant_id: str = Field(..., description="테넌트 고유 ID")
    freshdesk_domain: str = Field(..., description="Freshdesk 도메인 (예: company.freshdesk.com)")
    freshdesk_api_key: Optional[str] = Field(None, description="Freshdesk API 키 (마스킹됨)")

    # Gemini File Search 스토어 설정
    gemini_store_tickets: Optional[str] = Field(None, description="티켓 임베딩 스토어")
    gemini_store_articles: Optional[str] = Field(None, description="KB 문서 임베딩 스토어")
    gemini_store_common: Optional[str] = Field(None, description="공통 임베딩 스토어")

    # 기능 설정
    embedding_enabled: bool = Field(True, description="임베딩 검색 활성화 여부")
    analysis_depth: str = Field("full", description="분석 깊이 (quick, full)")
    llm_max_tokens: int = Field(1500, description="LLM 최대 토큰")

    # 동기화 설정
    sync_enabled: bool = Field(True, description="자동 동기화 활성화")
    sync_cron: str = Field("0 */6 * * *", description="동기화 크론 표현식 (기본: 6시간마다)")

    # Copilot 설정
    selected_fields: Optional[List[str]] = Field(default_factory=list, description="AI 제안 대상 필드 목록")
    response_tone: str = Field("formal", description="AI 응답 톤 (formal, casual)")

    # 메타데이터
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class TenantConfigCreate(BaseModel):
    """테넌트 생성 요청"""

    tenant_id: str = Field(..., description="테넌트 고유 ID")
    freshdesk_domain: str = Field(..., description="Freshdesk 도메인")
    freshdesk_api_key: str = Field(..., description="Freshdesk API 키")

    # 선택적 설정
    gemini_store_tickets: Optional[str] = None
    gemini_store_articles: Optional[str] = None
    gemini_store_common: Optional[str] = None
    embedding_enabled: bool = True
    analysis_depth: str = "full"
    llm_max_tokens: int = 1500
    sync_enabled: bool = True
    sync_cron: str = "0 */6 * * *"
    selected_fields: Optional[List[str]] = None
    response_tone: str = "formal"


class TenantConfigUpdate(BaseModel):
    """테넌트 업데이트 요청"""

    freshdesk_domain: Optional[str] = None
    freshdesk_api_key: Optional[str] = None
    gemini_store_tickets: Optional[str] = None
    gemini_store_articles: Optional[str] = None
    gemini_store_common: Optional[str] = None
    embedding_enabled: Optional[bool] = None
    analysis_depth: Optional[str] = None
    llm_max_tokens: Optional[int] = None
    sync_enabled: Optional[bool] = None
    sync_cron: Optional[str] = None
    selected_fields: Optional[List[str]] = None
    response_tone: Optional[str] = None


class TenantListResponse(BaseModel):
    """테넌트 목록 응답"""

    tenants: List[TenantConfig]
    total: int


# =============================================================================
# 동기화 모델
# =============================================================================

class SyncRequest(BaseModel):
    """동기화 요청"""

    since: Optional[str] = Field(None, description="이 시각 이후 업데이트된 항목만 (ISO 8601)")
    limit: int = Field(100, ge=1, le=500, description="최대 항목 수")
    sync_type: str = Field("all", description="동기화 유형 (tickets, articles, all)")


class SyncResult(BaseModel):
    """동기화 결과"""

    success: bool
    items_synced: int
    sync_type: str
    started_at: str
    completed_at: Optional[str] = None
    errors: List[str] = Field(default_factory=list)
    job_id: Optional[str] = None


class SyncStatus(BaseModel):
    """동기화 상태"""

    tenant_id: str
    last_ticket_sync: Optional[str] = None
    last_article_sync: Optional[str] = None
    total_tickets: int = 0
    total_articles: int = 0
    sync_in_progress: bool = False
    current_job_id: Optional[str] = None
    next_scheduled_sync: Optional[str] = None


class SyncJobStatus(BaseModel):
    """동기화 작업 상태"""

    job_id: str
    tenant_id: str
    status: str = Field(..., description="pending, running, completed, failed")
    sync_type: str
    started_at: str
    completed_at: Optional[str] = None
    items_synced: int = 0
    errors: List[str] = Field(default_factory=list)
    progress_percent: int = 0


# =============================================================================
# 스토어 모델
# =============================================================================

class StoreInfo(BaseModel):
    """Gemini File Search 스토어 정보"""

    store_name: str
    display_name: Optional[str] = None
    document_count: int = 0
    last_updated: Optional[str] = None
    size_bytes: Optional[int] = None


class StoreListResponse(BaseModel):
    """스토어 목록 응답"""

    stores: List[StoreInfo]
    total: int


class StoreDocumentUpload(BaseModel):
    """스토어 문서 업로드 요청"""

    store_name: str = Field(..., description="대상 스토어 이름")
    documents: List[Dict[str, Any]] = Field(..., description="업로드할 문서 목록")


class StoreDocumentUploadResult(BaseModel):
    """스토어 문서 업로드 결과"""

    store_name: str
    uploaded_count: int
    failed_count: int
    errors: List[str] = Field(default_factory=list)


# =============================================================================
# 통계 모델
# =============================================================================

class TenantStats(BaseModel):
    """테넌트 통계"""

    tenant_id: str
    total_proposals: int = 0
    approved_proposals: int = 0
    rejected_proposals: int = 0
    modified_proposals: int = 0
    approval_rate: float = 0.0
    average_analysis_time_ms: float = 0.0
    period_start: Optional[str] = None
    period_end: Optional[str] = None


# =============================================================================
# 스케줄러 모델
# =============================================================================

class SchedulerJobInfo(BaseModel):
    """스케줄러 작업 정보"""

    job_id: str
    tenant_id: str
    job_type: str = Field(..., description="sync_tickets, sync_articles, sync_all")
    cron_expression: str
    next_run_time: Optional[str] = None
    last_run_time: Optional[str] = None
    enabled: bool = True


class SchedulerStatus(BaseModel):
    """스케줄러 상태"""

    running: bool
    total_jobs: int
    jobs: List[SchedulerJobInfo]


class SchedulerJobCreate(BaseModel):
    """스케줄러 작업 생성 요청"""

    tenant_id: str
    job_type: str = Field("sync_all", description="sync_tickets, sync_articles, sync_all")
    cron_expression: str = Field("0 */6 * * *", description="크론 표현식")
    enabled: bool = True
