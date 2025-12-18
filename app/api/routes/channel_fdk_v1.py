from typing import Any, Dict, List, Optional

import json

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse

from app.core.config import get_settings
from app.middleware.tenant_auth import TenantContext, get_optional_tenant_context
from app.models.session import ChatRequest, ChatResponse
from app.services.chat_usecase import ChatUsecase, get_chat_usecase


router = APIRouter(prefix="/fdk/v1", tags=["channel:fdk"])


def _get_allowed_sources() -> set[str]:
    """
    FDK 채널에서 허용하는 sources:
    - 논리 키: tickets/articles/common (app/api/routes/health.py의 status 설명과 일치)
    - 설정된 실제 store name: settings.gemini_store_* (레거시 포함)
    """
    settings = get_settings()
    allowed: set[str] = {"tickets", "articles", "common"}
    for value in (
        settings.gemini_store_tickets,
        settings.gemini_store_articles,
        settings.gemini_store_common,
        getattr(settings, "gemini_common_store_name", None),  # legacy/test compatibility
    ):
        if value:
            allowed.add(value)
    return allowed


def _validate_sources(sources: Optional[List[str]]) -> None:
    if not sources:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="FDK 채널에서는 sources가 필수입니다.",
        )

    allowed = _get_allowed_sources()
    invalid = [s for s in sources if s not in allowed]
    if invalid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "INVALID_SOURCES",
                "message": "FDK 채널에서 허용되지 않는 sources가 포함되어 있습니다.",
                "invalid": invalid,
                "allowedSourceKeys": ["tickets", "articles", "common"],
            },
        )


def _format_sse(event: str, data: Dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@router.post("/chat", response_model=ChatResponse, response_model_by_alias=True)
async def fdk_chat(
    request: ChatRequest,
    tenant: Optional[TenantContext] = Depends(get_optional_tenant_context),
    usecase: ChatUsecase = Depends(get_chat_usecase),
) -> ChatResponse:
    """
    FDK 채널 BFF 엔드포인트.
    - 현재는 레거시 chat 동작과 동일(하위호환/점진 전환 목적)
    - 향후 채널별 기본값/검증/권한을 이 레이어에서만 추가
    """
    _validate_sources(request.sources)
    return await usecase.handle_legacy_chat(request, tenant=tenant)


@router.get("/chat/stream")
async def fdk_chat_stream(
    session_id: str = Query(..., alias="sessionId"),
    query: str = Query(...),
    rag_store_name: Optional[str] = Query(None, alias="ragStoreName"),
    sources: Optional[List[str]] = Query(None, alias="sources"),
    product: Optional[str] = Query(None, alias="product"),
    legacy_common_product: Optional[str] = Query(None, alias="commonProduct"),
    clarification_option: Optional[str] = Query(None, alias="clarificationOption"),
    tenant: Optional[TenantContext] = Depends(get_optional_tenant_context),
    usecase: ChatUsecase = Depends(get_chat_usecase),
) -> StreamingResponse:
    _validate_sources(sources)
    request = ChatRequest(
        sessionId=session_id,
        query=query,
        ragStoreName=rag_store_name,
        sources=sources or None,
        commonProduct=product or legacy_common_product,
        clarificationOption=clarification_option,
    )

    async def event_stream():
        async for event in usecase.stream_legacy_chat(request, tenant=tenant):
            yield _format_sse(event["event"], event["data"])

    return StreamingResponse(event_stream(), media_type="text/event-stream")
