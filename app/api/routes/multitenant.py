"""
Multitenant API Routes

These routes require tenant authentication (X-Tenant-ID, X-Platform, X-API-Key headers).
Used by platform-specific frontends (Freshdesk, Zendesk, etc.)
"""

from dataclasses import asdict
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
import json

from app.middleware.tenant_auth import TenantContext, get_tenant_context, get_optional_tenant_context
from app.models.session import ChatRequest, ChatResponse
from app.services.chat_usecase import ChatUsecase, get_chat_usecase
from app.services.multitenant_chat_handler import MultitenantChatHandler, get_multitenant_chat_handler
from app.services.session_repository import SessionRepository, get_session_repository

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
    handler: Optional[MultitenantChatHandler] = Depends(get_multitenant_chat_handler),
    repository: SessionRepository = Depends(get_session_repository),
) -> StreamingResponse:
    """
    Streaming multitenant chat endpoint.
    
    Requires authentication headers (same as POST /chat).
    """
    if not handler:
        async def error_stream():
            yield _format_sse("error", {"message": "Chat service not available"})
        return StreamingResponse(error_stream(), media_type="text/event-stream")
    
    request = ChatRequest(
        sessionId=session_id,
        query=query,
        sources=sources,
        commonProduct=product,
    )
    
    # Get conversation history (simplified for streaming)
    session = await repository.get(session_id)
    history: List[str] = []
    if session and isinstance(session, dict):
        raw_history = session.get("questionHistory", [])
        history = [str(entry) for entry in raw_history if isinstance(entry, str)][-4:]
    
    async def event_stream():
        response_text = ""
        async for event in handler.stream_handle(
            request,
            tenant,
            history=history,
        ):
            yield _format_sse(event["event"], event["data"])
            if event["event"] == "result":
                response_text = event["data"].get("text", "")
                await repository.append_turn(session_id, query, response_text)
    
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
