from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, status

from app.core.config import get_settings
from app.services.tenant_registry import TenantRegistry, get_tenant_registry

router = APIRouter(tags=["health"])


@router.get("/health")
def read_health() -> dict:
    return {
        "status": "ok",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/status")
def read_status(
    x_tenant_id: Optional[str] = Header(None, alias="X-Tenant-ID"),
    tenant_registry: TenantRegistry = Depends(get_tenant_registry),
) -> Dict[str, Any]:
    """
    시스템 상태 및 사용 가능한 검색 소스 반환
    
    FDK 앱에서 소스 선택 UI를 렌더링하기 위해 사용
    
    소스 구조:
    - tickets: 테넌트의 티켓 (기본)
    - articles: 테넌트의 헬프센터 문서 (기본)  
    - common: 공통 제품 문서 (옵션)
    """
    settings = get_settings()
    
    # 기본 소스: tickets, articles (항상 제공)
    available_sources: List[str] = ["tickets", "articles"]
    rag_store_names: Dict[str, Optional[str]] = {}
    
    # 테넌트별 설정이 있으면 적용
    tenant_config = None
    if x_tenant_id:
        try:
            tenant_config = tenant_registry.get(x_tenant_id)
        except HTTPException:
            # 테넌트가 없으면 기본 설정 사용
            pass
    
    if tenant_config:
        # 테넌트별 Gemini store 설정
        if tenant_config.gemini.store_names:
            for store in tenant_config.gemini.store_names:
                store_lower = store.lower()
                if "ticket" in store_lower:
                    rag_store_names["tickets"] = store
                elif "article" in store_lower:
                    rag_store_names["articles"] = store
                elif "common" in store_lower:
                    rag_store_names["common"] = store
    else:
        # 전역 설정 사용
        if settings.gemini_store_tickets:
            rag_store_names["tickets"] = settings.gemini_store_tickets
        if settings.gemini_store_articles:
            rag_store_names["articles"] = settings.gemini_store_articles
    
    # 공통 문서는 옵션 (설정되어 있으면 추가)
    if settings.gemini_store_common:
        available_sources.append("common")
        rag_store_names["common"] = settings.gemini_store_common
    
    return {
        "ready": True,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "tenantId": x_tenant_id,
        "availableSources": available_sources,
        "ragStoreNames": rag_store_names,
        "geminiModel": settings.gemini_primary_model,
    }
