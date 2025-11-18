from dataclasses import asdict
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException

from app.models.session import ChatRequest, ChatResponse
from app.services.common_chat_handler import CommonChatHandler, get_common_chat_handler
from app.services.query_filter_analyzer import QueryFilterAnalyzer, get_query_filter_analyzer
from app.services.ticket_chat_handler import TicketChatHandler, get_ticket_chat_handler
from app.services.pipeline_client import PipelineClient, PipelineClientError, get_pipeline_client
from app.services.session_repository import SessionRepository, get_session_repository

router = APIRouter(tags=["chat"])


def _handle_error(exc: PipelineClientError) -> HTTPException:
    return HTTPException(status_code=exc.status_code, detail=exc.details)


@router.post("/chat", response_model=ChatResponse, response_model_by_alias=True)
def chat(
    request: ChatRequest,
    pipeline: PipelineClient = Depends(get_pipeline_client),
    repository: SessionRepository = Depends(get_session_repository),
    common_handler: Optional[CommonChatHandler] = Depends(get_common_chat_handler),
    analyzer: Optional[QueryFilterAnalyzer] = Depends(get_query_filter_analyzer),
    ticket_handler: Optional[TicketChatHandler] = Depends(get_ticket_chat_handler),
) -> ChatResponse:
    session = repository.get(request.session_id)
    if not session:
        try:
            session = pipeline.get_session(request.session_id)
        except PipelineClientError as exc:
            raise _handle_error(exc)
        repository.save(session)

    conversation_history = session.get("questionHistory") if isinstance(session, dict) else []
    history_texts = []
    if isinstance(conversation_history, list):
        history_texts = [str(entry) for entry in conversation_history if isinstance(entry, str)]

    clarification_state = session.get("clarificationState") if isinstance(session, dict) else None
    if request.clarification_option and clarification_state and isinstance(session, dict):
        session.pop("clarificationState", None)
        repository.save(session)

    if common_handler and common_handler.can_handle(request):
        response = common_handler.handle(request, history=history_texts)
        repository.append_question(request.session_id, request.query)
        return response

    if ticket_handler and ticket_handler.can_handle(request):
        payload, ticket_result = ticket_handler.handle(
            request,
            history=history_texts,
            clarification_state=clarification_state,
        )
        if ticket_result:
            repository.record_analyzer_result(request.session_id, ticket_result)
        repository.append_question(request.session_id, request.query)
        return ChatResponse.model_validate(payload)

    analyzer_result = (
        analyzer.analyze(
            request.query,
            clarification_option=request.clarification_option,
            clarification_state=clarification_state,
        )
        if analyzer
        else None
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
        response = pipeline.chat(payload)
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
        repository.record_analyzer_result(request.session_id, analyzer_result)

    repository.append_question(request.session_id, request.query)
    return ChatResponse.model_validate(response)
