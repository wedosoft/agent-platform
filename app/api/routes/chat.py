from typing import Optional

from fastapi import APIRouter, Depends, HTTPException

from app.models.session import ChatRequest, ChatResponse
from app.services.common_chat_handler import CommonChatHandler, get_common_chat_handler
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

    if common_handler and common_handler.can_handle(request):
        response = common_handler.handle(request, history=history_texts)
        repository.append_question(request.session_id, request.query)
        return response

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

    repository.append_question(request.session_id, request.query)
    return ChatResponse.model_validate(response)
