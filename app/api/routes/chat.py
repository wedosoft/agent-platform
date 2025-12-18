from dataclasses import asdict
from typing import Any, Dict, List, Optional
import inspect
import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
import json

from app.models.session import ChatRequest, ChatResponse
from app.middleware.tenant_auth import TenantContext, get_optional_tenant_context
from app.services.common_chat_handler import CommonChatHandler, get_common_chat_handler
from app.services.multitenant_chat_handler import MultitenantChatHandler, get_multitenant_chat_handler
from app.services.query_filter_analyzer import QueryFilterAnalyzer, get_query_filter_analyzer
from app.services.pipeline_client import PipelineClient, PipelineClientError, get_pipeline_client
from app.services.ticket_chat_handler import TicketChatHandler, get_ticket_chat_handler
from app.services.session_repository import SessionRepository, get_session_repository

LOGGER = logging.getLogger(__name__)

router = APIRouter(tags=["chat"])


def _format_sse(event: str, data: Dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


async def _maybe_await(value):
    """Await the value if needed to support sync test doubles."""
    if inspect.isawaitable(value):
        return await value
    return value


@router.post("/chat", response_model=ChatResponse, response_model_by_alias=True)
async def chat(
    request: ChatRequest,
    repository: SessionRepository = Depends(get_session_repository),
    common_handler: Optional[CommonChatHandler] = Depends(get_common_chat_handler),
    analyzer: Optional[QueryFilterAnalyzer] = Depends(get_query_filter_analyzer),
    ticket_handler: Optional[TicketChatHandler] = Depends(get_ticket_chat_handler),
    pipeline: PipelineClient = Depends(get_pipeline_client),
    tenant: Optional[TenantContext] = Depends(get_optional_tenant_context),
    multitenant_handler: Optional[MultitenantChatHandler] = Depends(get_multitenant_chat_handler),
) -> ChatResponse:
    """통합 채팅 엔드포인트 - 모든 sources (tickets, articles, common) 처리"""
    
    # 세션 가져오기 또는 생성
    session = await repository.get(request.session_id)
    if not session:
        # 세션이 없으면 빈 세션 생성
        session = {"sessionId": request.session_id, "conversationHistory": [], "questionHistory": []}
        await repository.save(session)
    
    # 대화 히스토리
    conversation_history = []
    if session and isinstance(session, dict):
        conversation_history = session.get("conversationHistory", [])
    
    # common_handler가 처리 가능하면 직접 처리
    if common_handler and common_handler.can_handle(request):
        LOGGER.info("🎯 CommonChatHandler handling request for sources: %s", request.sources)
        response = await _maybe_await(common_handler.handle(request, history=conversation_history))
        # Save both question and answer as a turn
        await repository.append_turn(request.session_id, request.query, response.text or "")
        return response

    # ---------------------------------------------------------------------
    # Multitenant routing (when tenant auth headers are present)
    # - Keep backward compatibility for clients that used /api/chat with tenant headers.
    # - When tenant context is present, enforce tenant-isolated handler.
    # ---------------------------------------------------------------------
    if tenant is not None:
        if not multitenant_handler:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Chat service not available. Check Gemini API configuration.",
            )

        additional_filters = []
        if analyzer:
            analyzer_result = await _maybe_await(analyzer.analyze(request.query))
            if analyzer_result and getattr(analyzer_result, "filters", None):
                additional_filters = analyzer_result.filters

        response = await multitenant_handler.handle(
            request,
            tenant,
            history=conversation_history,
            additional_filters=additional_filters,
        )
        await repository.append_turn(request.session_id, request.query, response.text or "")
        return response
    
    # ticket_handler 처리
    history_texts = []
    if isinstance(session, dict):
        question_history = session.get("questionHistory", [])
        if isinstance(question_history, list):
            history_texts = [str(entry) for entry in question_history if isinstance(entry, str)]

    clarification_state = session.get("clarificationState") if isinstance(session, dict) else None
    if request.clarification_option and clarification_state and isinstance(session, dict):
        session.pop("clarificationState", None)
        await repository.save(session)

    if ticket_handler and ticket_handler.can_handle(request):
        LOGGER.info("🎫 TicketChatHandler handling request")
        payload, ticket_result = await _maybe_await(
            ticket_handler.handle(
                request,
                history=history_texts,
                clarification_state=clarification_state,
            )
        )
        if ticket_result:
            await repository.record_analyzer_result(request.session_id, ticket_result)
        await repository.append_question(request.session_id, request.query)
        return ChatResponse.model_validate(payload)

    # ---------------------------------------------------------------------
    # Pipeline fallback (legacy)
    # - tests/conftest.py에서 common/ticket handler를 비활성화하므로,
    #   여기로 떨어져야 /api/chat 이 400이 아니라 200으로 동작함.
    # - 실제 환경에서는 기존 Node pipeline과의 호환을 위해 유지.
    # ---------------------------------------------------------------------
    analyzer_result = None
    if analyzer:
        try:
            analyzer_result = await _maybe_await(
                analyzer.analyze(
                    request.query,
                    clarification_option=request.clarification_option,
                    clarification_state=clarification_state,
                )
            )
        except Exception:
            analyzer_result = None

    if analyzer_result:
        await repository.record_analyzer_result(request.session_id, analyzer_result)

    payload = request.model_dump(by_alias=True, exclude_none=True)
    try:
        pipeline_result = await _maybe_await(pipeline.chat(payload))
    except PipelineClientError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.details)

    # Persist question history (tests expect questionHistory append)
    await repository.append_question(request.session_id, request.query)

    if isinstance(pipeline_result, dict):
        # Maintain minimal shape
        pipeline_result.setdefault("sources", request.sources)

        if analyzer_result:
            pipeline_result["filters"] = analyzer_result.summaries or pipeline_result.get("filters") or []
            pipeline_result["filterConfidence"] = analyzer_result.confidence
            pipeline_result["clarificationNeeded"] = analyzer_result.clarification_needed
            pipeline_result["clarification"] = asdict(analyzer_result.clarification) if analyzer_result.clarification else None
            pipeline_result["knownContext"] = analyzer_result.known_context or {}

    return ChatResponse.model_validate(pipeline_result)

    # 처리할 수 있는 핸들러가 없음
    LOGGER.error("❌ No handler available for sources: %s", request.sources)
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail={"error": f"지원하지 않는 검색 소스입니다: {request.sources}"}
    )


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
