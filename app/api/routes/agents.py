from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.config import get_settings
from app.models.session import ChatRequest, ChatResponse, SessionCreateResponse
from app.services.agent_chat_service import AgentChatService, get_agent_chat_service
from app.services.session_repository import SessionRepository, get_session_repository
from app.services.tenant_registry import TenantRegistry, get_tenant_registry

router = APIRouter(prefix="/agents", tags=["agents"])


def _build_history(session: Optional[dict]) -> List[str]:
    if not session:
        return []
    history = session.get("questionHistory")
    if isinstance(history, list):
        return [str(entry) for entry in history if isinstance(entry, str)]
    return []


@router.post("/{tenant_id}/session", response_model=SessionCreateResponse, response_model_by_alias=True, status_code=201)
async def create_agent_session(
    tenant_id: str,
    registry: TenantRegistry = Depends(get_tenant_registry),
    repository: SessionRepository = Depends(get_session_repository),
) -> SessionCreateResponse:
    registry.get(tenant_id)  # 존재 여부 확인용
    settings = get_settings()
    session_id = uuid4().hex
    now = datetime.now(timezone.utc)
    now_iso = now.isoformat()
    record = {
        "sessionId": session_id,
        "createdAt": now_iso,
        "updatedAt": now_iso,
        "tenantId": tenant_id,
        "questionHistory": [],
    }
    await repository.save(record)
    return SessionCreateResponse(
        session_id=session_id,
        created_at=now,
        ttl_minutes=settings.session_ttl_minutes,
        tenant_id=tenant_id,
    )


@router.get("/{tenant_id}/status")
async def agent_status(
    tenant_id: str,
    registry: TenantRegistry = Depends(get_tenant_registry),
):
    tenant = registry.get(tenant_id)
    return {
        "tenantId": tenant.id,
        "product": tenant.product,
        "pipelineType": tenant.pipeline_type,
        "storeNames": tenant.gemini.store_names,
        "metadataFilters": [filter_.model_dump() for filter_ in tenant.metadata_filters],
        "ready": bool(tenant.gemini.store_names),
    }


@router.post("/{tenant_id}/chat", response_model=ChatResponse, response_model_by_alias=True)
async def agent_chat(
    tenant_id: str,
    request: ChatRequest,
    registry: TenantRegistry = Depends(get_tenant_registry),
    repository: SessionRepository = Depends(get_session_repository),
    chat_service: AgentChatService = Depends(get_agent_chat_service),
) -> ChatResponse:
    tenant = registry.get(tenant_id)
    session = await repository.get(request.session_id)
    if not session:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="세션을 찾을 수 없습니다.")
    session_tenant = session.get("tenantId")
    if session_tenant and session_tenant != tenant_id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="세션이 다른 에이전트에 속해 있습니다.")
    history = _build_history(session)
    clarification_state = session.get("clarificationState") if isinstance(session, dict) else None

    payload, analyzer_result = await chat_service.chat(
        tenant=tenant,
        request=request,
        history=history,
        clarification_state=clarification_state,
    )

    await repository.record_analyzer_result(request.session_id, analyzer_result)
    await repository.append_question(request.session_id, request.query)

    return ChatResponse.model_validate(payload)
