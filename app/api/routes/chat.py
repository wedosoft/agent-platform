from typing import Any, Dict, List, Optional
import logging

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
import json

from app.models.session import ChatRequest, ChatResponse
from app.middleware.tenant_auth import TenantContext, get_optional_tenant_context
from app.services.chat_usecase import ChatUsecase, get_chat_usecase
from app.services.common_chat_handler import CommonChatHandler, get_common_chat_handler
from app.services.multitenant_chat_handler import MultitenantChatHandler, get_multitenant_chat_handler
from app.services.session_repository import SessionRepository, get_session_repository

LOGGER = logging.getLogger(__name__)

router = APIRouter(tags=["chat"])


def _format_sse(event: str, data: Dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@router.post("/chat", response_model=ChatResponse, response_model_by_alias=True)
async def chat(
    request: ChatRequest,
    tenant: Optional[TenantContext] = Depends(get_optional_tenant_context),
    usecase: ChatUsecase = Depends(get_chat_usecase),
) -> ChatResponse:
    """통합 채팅 엔드포인트 - 기존 API 유지(채널 BFF도 동일 핸들러 재사용)."""
    return await usecase.handle_legacy_chat(request, tenant=tenant)


@router.get("/chat/stream")
async def chat_stream(
    session_id: str = Query(..., alias="sessionId"),
    query: str = Query(...),
    rag_store_name: Optional[str] = Query(None, alias="ragStoreName"),
    sources: Optional[List[str]] = Query(None, alias="sources"),
    product: Optional[str] = Query(None, alias="product"),
    legacy_common_product: Optional[str] = Query(None, alias="commonProduct"),
    clarification_option: Optional[str] = Query(None, alias="clarificationOption"),
    repository: SessionRepository = Depends(get_session_repository),
    common_handler: Optional[CommonChatHandler] = Depends(get_common_chat_handler),
    tenant: Optional[TenantContext] = Depends(get_optional_tenant_context),
    multitenant_handler: Optional[MultitenantChatHandler] = Depends(get_multitenant_chat_handler),
) -> StreamingResponse:
    effective_product = product or legacy_common_product

    request = ChatRequest(
        sessionId=session_id,
        query=query,
        ragStoreName=rag_store_name,
        sources=sources or None,
        commonProduct=effective_product,
        clarificationOption=clarification_option,
    )

    session = await repository.get(request.session_id)
    if not session:
        # 세션이 없으면 빈 세션 생성
        session = {"sessionId": request.session_id, "conversationHistory": [], "questionHistory": []}
        await repository.save(session)

    # Use conversationHistory (with roles) if available
    conversation_history: List[dict] = []
    if isinstance(session, dict):
        conversation_history = session.get("conversationHistory", [])
        # Keep only last 4 turns (2 Q&A pairs) for streaming to reduce latency
        if len(conversation_history) > 4:
            conversation_history = conversation_history[-4:]

    async def event_stream():
        if tenant is not None:
            if not multitenant_handler:
                yield _format_sse("error", {"message": "Chat service not available"})
                return

            raw_history = session.get("questionHistory", []) if isinstance(session, dict) else []
            history_texts = [str(entry) for entry in raw_history if isinstance(entry, str)][-4:]

            response_text = ""
            async for event in multitenant_handler.stream_handle(
                request,
                tenant,
                history=history_texts,
            ):
                yield _format_sse(event["event"], event["data"])
                if event["event"] == "result":
                    response_text = event["data"].get("text", "")
                    await repository.append_turn(request.session_id, request.query, response_text)
            return

        if not common_handler or not common_handler.can_handle(request):
            yield _format_sse("error", {"message": f"지원하지 않는 검색 소스입니다: {request.sources}"})
            return

        terminal_event_sent = False
        response_text = ""
        async for event in common_handler.stream_handle(request, history=conversation_history):
            yield _format_sse(event["event"], event["data"])
            if event["event"] == "result":
                terminal_event_sent = True
                response_text = event["data"].get("text", "")
                # Save both question and answer as a turn
                await repository.append_turn(request.session_id, request.query, response_text)
            if event["event"] == "error":
                terminal_event_sent = True
                break
        if not terminal_event_sent:
            yield _format_sse("error", {"message": "잠시 후 다시 시도해 주세요."})

    return StreamingResponse(event_stream(), media_type="text/event-stream")
