from dataclasses import asdict
from typing import Any, Dict, List, Optional
import inspect

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
import json

from app.models.session import ChatRequest, ChatResponse
from app.services.common_chat_handler import CommonChatHandler, get_common_chat_handler
from app.services.query_filter_analyzer import QueryFilterAnalyzer, get_query_filter_analyzer
from app.services.ticket_chat_handler import TicketChatHandler, get_ticket_chat_handler
from app.services.pipeline_client import PipelineClient, PipelineClientError, get_pipeline_client
from app.services.session_repository import SessionRepository, get_session_repository

router = APIRouter(tags=["chat"])


def _format_sse(event: str, data: Dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _handle_error(exc: PipelineClientError) -> HTTPException:
    return HTTPException(status_code=exc.status_code, detail=exc.details)


async def _maybe_await(value):
    """Await the value if needed to support sync test doubles."""
    if inspect.isawaitable(value):
        return await value
    return value


@router.post("/chat", response_model=ChatResponse, response_model_by_alias=True)
async def chat(
    request: ChatRequest,
    pipeline: PipelineClient = Depends(get_pipeline_client),
    repository: SessionRepository = Depends(get_session_repository),
    common_handler: Optional[CommonChatHandler] = Depends(get_common_chat_handler),
    analyzer: Optional[QueryFilterAnalyzer] = Depends(get_query_filter_analyzer),
    ticket_handler: Optional[TicketChatHandler] = Depends(get_ticket_chat_handler),
) -> ChatResponse:
    # common_handler가 처리 가능하면 Pipeline 없이 직접 처리
    if common_handler and common_handler.can_handle(request):
        session = await repository.get(request.session_id)
        conversation_history = session.get("questionHistory") if session and isinstance(session, dict) else []
        history_texts = []
        if isinstance(conversation_history, list):
            history_texts = [str(entry) for entry in conversation_history if isinstance(entry, str)]
        
        response = await _maybe_await(common_handler.handle(request, history=history_texts))
        await repository.append_question(request.session_id, request.query)
        return response
    
    session = await repository.get(request.session_id)
    if not session:
        try:
            session = await _maybe_await(pipeline.get_session(request.session_id))
        except PipelineClientError as exc:
            raise _handle_error(exc)
        await repository.save(session)

    conversation_history = session.get("questionHistory") if isinstance(session, dict) else []
    history_texts = []
    if isinstance(conversation_history, list):
        history_texts = [str(entry) for entry in conversation_history if isinstance(entry, str)]

    clarification_state = session.get("clarificationState") if isinstance(session, dict) else None
    if request.clarification_option and clarification_state and isinstance(session, dict):
        session.pop("clarificationState", None)
        await repository.save(session)

    if ticket_handler and ticket_handler.can_handle(request):
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

    analyzer_result = None
    if analyzer:
        analyzer_result = await _maybe_await(
            analyzer.analyze(
                request.query,
                clarification_option=request.clarification_option,
                clarification_state=clarification_state,
            )
        )

    payload = {
        "query": request.query,
        "sessionId": request.session_id,
    }
    if request.rag_store_name:
        payload["ragStoreName"] = request.rag_store_name
    if request.sources:
        payload["sources"] = request.sources
    if request.common_product:
        payload["commonProduct"] = request.common_product

    try:
        response = await _maybe_await(pipeline.chat(payload))
    except PipelineClientError as exc:
        raise _handle_error(exc)

    if analyzer_result:
        if analyzer_result.summaries and not response.get("filters"):
            response["filters"] = analyzer_result.summaries
        if analyzer_result.clarification_needed and analyzer_result.clarification:
            response["clarificationNeeded"] = True
            response["clarification"] = asdict(analyzer_result.clarification)
        if analyzer_result.confidence and not response.get("filterConfidence"):
            response["filterConfidence"] = analyzer_result.confidence
        await repository.record_analyzer_result(request.session_id, analyzer_result)

    await repository.append_question(request.session_id, request.query)
    return ChatResponse.model_validate(response)


@router.get("/chat/stream")
async def chat_stream(
    session_id: str = Query(..., alias="sessionId"),
    query: str = Query(...),
    rag_store_name: Optional[str] = Query(None, alias="ragStoreName"),
    sources: Optional[List[str]] = Query(None, alias="sources"),
    product: Optional[str] = Query(None, alias="product"),
    legacy_common_product: Optional[str] = Query(None, alias="commonProduct"),
    clarification_option: Optional[str] = Query(None, alias="clarificationOption"),
    pipeline: PipelineClient = Depends(get_pipeline_client),
    repository: SessionRepository = Depends(get_session_repository),
    common_handler: Optional[CommonChatHandler] = Depends(get_common_chat_handler),
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
        try:
            session = await _maybe_await(pipeline.get_session(request.session_id))
        except PipelineClientError as exc:
            raise _handle_error(exc)
        await repository.save(session)

    conversation_history = session.get("questionHistory") if isinstance(session, dict) else []
    history_texts: List[str] = []
    if isinstance(conversation_history, list):
        snapshots = [str(entry) for entry in conversation_history if isinstance(entry, str)]
        history_texts = snapshots[-2:]

    async def event_stream():
        if not common_handler or not common_handler.can_handle(request):
            yield _format_sse("error", {"message": "현재 공통 문서 질문만 지원합니다."})
            return

        terminal_event_sent = False
        async for event in common_handler.stream_handle(request, history=history_texts):
            yield _format_sse(event["event"], event["data"])
            if event["event"] == "result":
                terminal_event_sent = True
                await repository.append_question(request.session_id, request.query)
            if event["event"] == "error":
                terminal_event_sent = True
                break
        if not terminal_event_sent:
            yield _format_sse("error", {"message": "잠시 후 다시 시도해 주세요."})

    return StreamingResponse(event_stream(), media_type="text/event-stream")
