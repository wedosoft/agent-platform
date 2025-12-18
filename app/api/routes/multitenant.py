"""
Multitenant API Routes

These routes require tenant authentication (X-Tenant-ID, X-Platform, X-API-Key headers).
Used by platform-specific frontends (Freshdesk, Zendesk, etc.)
"""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
import json

from app.middleware.tenant_auth import TenantContext, get_tenant_context, get_optional_tenant_context
from app.models.session import ChatRequest, ChatResponse
from app.services.chat_usecase import ChatUsecase, get_chat_usecase
from app.services.multitenant_chat_handler import MultitenantChatHandler, get_multitenant_chat_handler

router = APIRouter(tags=["multitenant"])


def _format_sse(event: str, data: Dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@router.post("/chat", response_model=ChatResponse)
async def multitenant_chat(
    request: ChatRequest,
    tenant: TenantContext = Depends(get_tenant_context),
    handler: Optional[MultitenantChatHandler] = Depends(get_multitenant_chat_handler),
    usecase: ChatUsecase = Depends(get_chat_usecase),
) -> ChatResponse:
    """
    Multitenant chat endpoint.
    
    Requires authentication headers:
    - X-Tenant-ID: Tenant identifier
    - X-Platform: Platform type (freshdesk, zendesk, etc.)
    - X-API-Key: Platform API key
    
    Automatically applies tenant isolation filters to all searches.
    """
    if not handler:
        raise HTTPException(
            status_code=503,
            detail="Chat service not available. Check Gemini API configuration.",
        )

    return await usecase.handle_multitenant_chat(request, tenant=tenant)


@router.get("/chat/stream")
async def multitenant_chat_stream(
    session_id: str = Query(..., alias="sessionId"),
    query: str = Query(...),
    sources: Optional[List[str]] = Query(None),
    product: Optional[str] = Query(None),
    tenant: TenantContext = Depends(get_tenant_context),
    usecase: ChatUsecase = Depends(get_chat_usecase),
) -> StreamingResponse:
    """
    Streaming multitenant chat endpoint.
    
    Requires authentication headers (same as POST /chat).
    """
    request = ChatRequest(
        sessionId=session_id,
        query=query,
        sources=sources,
        commonProduct=product,
    )

    async def event_stream():
        async for event in usecase.stream_multitenant_chat(request, tenant=tenant):
            yield _format_sse(event["event"], event["data"])
    
    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.get("/tenant/info")
async def get_tenant_info(
    tenant: TenantContext = Depends(get_tenant_context),
) -> Dict[str, Any]:
    """
    Get information about the authenticated tenant.
    
    Useful for debugging and verifying authentication.
    """
    return {
        "tenant_id": tenant.tenant_id,
        "platform": tenant.platform,
        "domain": tenant.domain,
        "verified": tenant.verified,
        "mandatory_filter_count": len(tenant.mandatory_filters),
    }


@router.get("/health")
async def health_check(
    tenant: Optional[TenantContext] = Depends(get_optional_tenant_context),
) -> Dict[str, Any]:
    """
    Health check endpoint.
    
    Works with or without tenant authentication.
    """
    return {
        "status": "healthy",
        "authenticated": tenant is not None,
        "tenant_id": tenant.tenant_id if tenant else None,
    }
