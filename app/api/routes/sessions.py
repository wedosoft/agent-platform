from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException

from app.core.config import get_settings
from app.models.session import SessionCreateResponse, SessionDetailResponse
from app.services.session_repository import SessionRepository, get_session_repository

router = APIRouter(tags=["sessions"])


@router.post("/session", response_model=SessionCreateResponse, response_model_by_alias=True, status_code=201)
def create_session(repository: SessionRepository = Depends(get_session_repository)) -> SessionCreateResponse:
    settings = get_settings()
    session_id = uuid4().hex
    now = datetime.now(timezone.utc).isoformat()
    record = {
        "sessionId": session_id,
        "createdAt": now,
        "updatedAt": now,
        "questionHistory": [],
    }
    repository.save(record)
    return SessionCreateResponse(
        session_id=session_id,
        created_at=now,
        ttl_minutes=settings.session_ttl_minutes,
    )


@router.get("/session/{session_id}", response_model=SessionDetailResponse, response_model_by_alias=True)
def get_session(
    session_id: str,
    repository: SessionRepository = Depends(get_session_repository),
) -> SessionDetailResponse:
    payload = repository.get(session_id)
    if not payload:
        raise HTTPException(status_code=404, detail="session not found or expired")
    return SessionDetailResponse.model_validate(payload)
