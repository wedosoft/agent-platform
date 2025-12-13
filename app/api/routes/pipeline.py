import inspect

from fastapi import APIRouter, Depends, HTTPException

from app.core.config import get_settings
from app.models.pipeline import PipelineStatusResponse, SyncRequest, SyncResponse
from app.services.pipeline_client import PipelineClient, PipelineClientError, get_pipeline_client

router = APIRouter(tags=["pipeline"])


async def _maybe_await(value):
    """Await the value if needed to support sync test doubles."""
    if inspect.isawaitable(value):
        return await value
    return value


def _handle_pipeline_error(exc: PipelineClientError) -> HTTPException:
    return HTTPException(status_code=exc.status_code, detail=exc.details)


@router.get("/status", response_model=PipelineStatusResponse, response_model_by_alias=True)
def get_status() -> PipelineStatusResponse:
    settings = get_settings()
    rag_store_names = {}
    if settings.gemini_store_common:
        rag_store_names["common"] = settings.gemini_store_common
    if settings.gemini_store_tickets:
        rag_store_names["tickets"] = settings.gemini_store_tickets
    if settings.gemini_store_articles:
        rag_store_names["articles"] = settings.gemini_store_articles

    available_sources = [value for value in rag_store_names.values() if value]

    payload = {
        "ready": bool(available_sources),
        "ragStoreName": available_sources[0] if available_sources else None,
        "ragStoreNames": rag_store_names or None,
        "lastSync": None,
        "progress": None,
        "storeStats": None,
        "availableSources": available_sources,
    }
    return PipelineStatusResponse.model_validate(payload)


@router.post("/sync", response_model=SyncResponse, response_model_by_alias=True)
async def trigger_sync(request: SyncRequest, pipeline: PipelineClient = Depends(get_pipeline_client)) -> SyncResponse:
    payload = request.model_dump(by_alias=True, exclude_none=True)
    try:
        result = await _maybe_await(pipeline.trigger_sync(payload))
    except PipelineClientError as exc:
        raise _handle_pipeline_error(exc)
    return SyncResponse.model_validate(result)
