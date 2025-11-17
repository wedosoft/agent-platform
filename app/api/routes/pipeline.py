from fastapi import APIRouter, Depends, HTTPException

from app.models.pipeline import PipelineStatusResponse, SyncRequest, SyncResponse
from app.services.pipeline_client import PipelineClient, PipelineClientError, get_pipeline_client

router = APIRouter(tags=["pipeline"])


def _handle_pipeline_error(exc: PipelineClientError) -> HTTPException:
    return HTTPException(status_code=exc.status_code, detail=exc.details)


@router.get("/status", response_model=PipelineStatusResponse, response_model_by_alias=True)
def get_status(pipeline: PipelineClient = Depends(get_pipeline_client)) -> PipelineStatusResponse:
    try:
        result = pipeline.get_status()
    except PipelineClientError as exc:
        raise _handle_pipeline_error(exc)
    return PipelineStatusResponse.model_validate(result)


@router.post("/sync", response_model=SyncResponse, response_model_by_alias=True)
def trigger_sync(request: SyncRequest, pipeline: PipelineClient = Depends(get_pipeline_client)) -> SyncResponse:
    payload = request.model_dump(by_alias=True, exclude_none=True)
    try:
        result = pipeline.trigger_sync(payload)
    except PipelineClientError as exc:
        raise _handle_pipeline_error(exc)
    return SyncResponse.model_validate(result)
