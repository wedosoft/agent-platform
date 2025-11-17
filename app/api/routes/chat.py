from fastapi import APIRouter, Depends, HTTPException

from app.models.session import ChatRequest, ChatResponse
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
) -> ChatResponse:
    session = repository.get(request.session_id)
    if not session:
        try:
            session = pipeline.get_session(request.session_id)
        except PipelineClientError as exc:
            raise _handle_error(exc)
        repository.save(session)

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
