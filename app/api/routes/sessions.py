from fastapi import APIRouter, Depends, HTTPException

from app.models.session import SessionCreateResponse, SessionDetailResponse
from app.services.pipeline_client import PipelineClient, PipelineClientError, get_pipeline_client
from app.services.session_repository import SessionRepository, get_session_repository

router = APIRouter(tags=["sessions"])


def _handle_pipeline_error(exc: PipelineClientError) -> HTTPException:
    return HTTPException(status_code=exc.status_code, detail=exc.details)


@router.post("/session", response_model=SessionCreateResponse, response_model_by_alias=True, status_code=201)
def create_session(
    pipeline: PipelineClient = Depends(get_pipeline_client),
    repository: SessionRepository = Depends(get_session_repository),
) -> SessionCreateResponse:
    try:
        payload = pipeline.create_session()
    except PipelineClientError as exc:
        raise _handle_pipeline_error(exc)

    repository.save(payload)
    return SessionCreateResponse.model_validate(payload)


@router.get("/session/{session_id}", response_model=SessionDetailResponse, response_model_by_alias=True)
def get_session(
    session_id: str,
    pipeline: PipelineClient = Depends(get_pipeline_client),
    repository: SessionRepository = Depends(get_session_repository),
) -> SessionDetailResponse:
    payload = repository.get(session_id)
    if not payload:
        try:
            payload = pipeline.get_session(session_id)
        except PipelineClientError as exc:
            raise _handle_pipeline_error(exc)
        repository.save(payload)
    return SessionDetailResponse.model_validate(payload)
