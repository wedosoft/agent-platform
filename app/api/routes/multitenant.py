"""
Multitenant API Routes

These routes require tenant authentication (X-Tenant-ID, X-Platform, X-API-Key headers).
Used by platform-specific frontends (Freshdesk, Zendesk, etc.)
"""

from dataclasses import asdict
from typing import Any, Dict, List, Optional
import inspect

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
import json

from app.middleware.tenant_auth import TenantContext, get_tenant_context, get_optional_tenant_context
from app.models.session import ChatRequest, ChatResponse
from app.services.multitenant_chat_handler import MultitenantChatHandler, get_multitenant_chat_handler
from app.services.query_filter_analyzer import QueryFilterAnalyzer, get_query_filter_analyzer
from app.services.session_repository import SessionRepository, get_session_repository

router = APIRouter(tags=["multitenant"])


def _format_sse(event: str, data: Dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


async def _maybe_await(value):
    """Await the value if needed to support sync/async hybrid analyzers."""
    if inspect.isawaitable(value):
        return await value
    return value


@router.post("/chat", response_model=ChatResponse)
async def multitenant_chat(
    request: ChatRequest,
    tenant: TenantContext = Depends(get_tenant_context),
    handler: Optional[MultitenantChatHandler] = Depends(get_multitenant_chat_handler),
    analyzer: Optional[QueryFilterAnalyzer] = Depends(get_query_filter_analyzer),
    repository: SessionRepository = Depends(get_session_repository),
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
    
    # Get conversation history
    session = await repository.get(request.session_id)
    conversation_history = []
    if session and isinstance(session, dict):
        conversation_history = session.get("conversationHistory", [])
    
    # Analyze query for additional filters
    additional_filters = []
    analyzer_result = None
    if analyzer:
        analyzer_result = await _maybe_await(analyzer.analyze(request.query))
        if analyzer_result and analyzer_result.filters:
            additional_filters = analyzer_result.filters
    
    # Handle chat with tenant context
    response = await handler.handle(
        request,
        tenant,
        history=conversation_history,
        additional_filters=additional_filters,
    )
    
    # Save conversation turn
    await repository.append_turn(
        request.session_id,
        request.query,
        response.text or "",
    )
    
    # Add analyzer result info to response if available
    if analyzer_result:
        if analyzer_result.summaries and not response.filters:
            response.filters = analyzer_result.summaries
        if analyzer_result.confidence:
            response.filter_confidence = analyzer_result.confidence
    
    return response


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
