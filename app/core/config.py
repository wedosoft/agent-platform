from __future__ import annotations

from functools import lru_cache
from typing import List, Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """기본 FastAPI 설정과 공통 환경 변수를 관리"""

    api_prefix: str = "/api"
    app_name: str = "Agent Platform Backend"
    log_level: str = "INFO"
    session_ttl_minutes: int = 30
    pipeline_base_url: str = "http://localhost:4000/pipeline"
    redis_url: Optional[str] = None
    redis_session_prefix: str = "agent-platform-session"

    # Admin API
    admin_api_key: Optional[str] = None

    # Supabase Auth (Google OAuth)
    supabase_jwt_secret: Optional[str] = None  # Supabase JWT Secret for token verification

    # Supabase (공통 문서)
    supabase_common_url: Optional[str] = None
    supabase_common_service_role_key: Optional[str] = None
    supabase_common_table_name: str = "documents"
    supabase_common_default_product: Optional[str] = None
    supabase_common_batch_size: int = 50
    supabase_common_languages: List[str] = Field(default_factory=lambda: ["ko", "en"])
    supabase_common_max_document_chars: int = 4000
    supabase_common_chunk_overlap: int = 200
    supabase_common_summary_enabled: bool = False
    supabase_common_summary_max_chars: int = 500

    # Gemini / RAG (공통 환경변수: GEMINI_STORE_*)
    gemini_api_key: Optional[str] = None
    gemini_primary_model: str = Field(default="gemini-2.5-flash")
    gemini_fallback_model: Optional[str] = Field(default="gemini-2.0-flash")
    gemini_store_tickets: Optional[str] = None
    gemini_store_articles: Optional[str] = None
    gemini_store_common: Optional[str] = None
    gemini_store_onboarding: Optional[str] = None  # 온보딩 인수인계 문서

    # Freshdesk
    freshdesk_domain: Optional[str] = None
    freshdesk_api_key: Optional[str] = None

    # Multi-tenant config (JSON or file path)
    tenant_config: Optional[str] = None
    tenant_config_path: Optional[str] = None

    model_config = SettingsConfigDict(
        env_prefix="",  # 프리픽스 없음 - GEMINI_*, SUPABASE_COMMON_* 직접 사용
        env_file=(".env", ".env.local"),
        env_file_encoding="utf-8",
    )

    @field_validator("supabase_common_languages", mode="before")
    @classmethod
    def split_languages(cls, value):
        if isinstance(value, str):
            items = [item.strip() for item in value.split(",") if item.strip()]
            return items or ["ko", "en"]
        if value is None:
            return ["ko", "en"]
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
