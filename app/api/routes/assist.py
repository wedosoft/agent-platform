"""
AI Assistant API 라우트

FDK Custom App에서 호출하는 티켓 분석, 승인, 수정 엔드포인트
SSE 스트리밍을 통한 실시간 진행 상황 업데이트 지원
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any, AsyncGenerator, Dict, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, status
from fastapi.responses import StreamingResponse

from app.models.assist import (
    AnalyzeRequest,
    AnalyzeResponse,
    ApproveRequest,
    ApproveResponse,
    RefineRequest,
    RefineResponse,
    Proposal,
)
from app.services.assist_service import AssistService, get_assist_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/assist", tags=["assist"])


# =============================================================================
# SSE Streaming Helper
# =============================================================================

async def sse_generator(
    events: AsyncGenerator[Dict[str, Any], None]
) -> AsyncGenerator[str, None]:
    """
    이벤트 스트림을 SSE 포맷으로 변환

    Args:
        events: 이벤트 딕셔너리의 비동기 제너레이터

    Yields:
        SSE 포맷 문자열

    Format:
        data: {"type": "event_name", "data": {...}}\n\n
    """
    last_heartbeat = time.time()

    try:
        async for event in events:
            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

            # 30초마다 하트비트 전송
            if time.time() - last_heartbeat > 30:
                heartbeat = {"type": "heartbeat", "timestamp": time.time()}
                yield f"data: {json.dumps(heartbeat)}\n\n"
                last_heartbeat = time.time()

    except Exception as e:
        logger.error(f"SSE 스트리밍 오류: {e}")
        error_event = {
            "type": "error",
            "message": str(e),
            "recoverable": False
        }
        yield f"data: {json.dumps(error_event)}\n\n"


# =============================================================================
# Routes
# =============================================================================

@router.post("/analyze")
async def analyze_ticket(
    request: AnalyzeRequest,
    x_tenant_id: str = Header(..., alias="X-Tenant-ID"),
    x_freshdesk_domain: Optional[str] = Header(None, alias="X-Freshdesk-Domain"),
    x_freshdesk_api_key: Optional[str] = Header(None, alias="X-Freshdesk-API-Key"),
    assist_service: AssistService = Depends(get_assist_service),
):
    """
    티켓 분석 및 AI 제안 생성

    Args:
        request: 분석 요청 (ticket_id, stream_progress 등)
        x_tenant_id: 테넌트 ID (헤더)
        x_freshdesk_domain: Freshdesk 도메인 (FDK에서 전달)
        x_freshdesk_api_key: Freshdesk API 키 (FDK에서 전달)

    Returns:
        스트리밍 모드: SSE 이벤트 스트림
        일반 모드: JSON 응답

    SSE 이벤트:
        - router_decision: 라우팅 결정
        - retriever_start: 검색 시작
        - retriever_results: 검색 결과
        - resolution_start: 솔루션 생성 시작
        - resolution_complete: 솔루션 완료
        - heartbeat: 연결 유지
        - error: 에러 발생
    """
    try:
        # FDK에서 전달받은 Freshdesk 자격 증명으로 컨텍스트 설정
        freshdesk_context = None
        if x_freshdesk_domain and x_freshdesk_api_key:
            freshdesk_context = {
                "domain": x_freshdesk_domain,
                "api_key": x_freshdesk_api_key,
            }

        if request.stream_progress:
            # SSE 스트리밍 응답
            events = assist_service.analyze_with_streaming(
                tenant_id=x_tenant_id,
                request=request,
                freshdesk_context=freshdesk_context,
            )
            return StreamingResponse(
                sse_generator(events),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "X-Accel-Buffering": "no",  # nginx 버퍼링 비활성화
                },
            )
        else:
            # 일반 JSON 응답
            proposal = await assist_service.analyze(
                tenant_id=x_tenant_id,
                request=request,
                freshdesk_context=freshdesk_context,
            )
            return AnalyzeResponse(proposal=proposal)

    except Exception as e:
        logger.error(f"분석 오류: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"분석 실패: {str(e)}",
        )


@router.post("/approve", response_model=ApproveResponse)
async def approve_proposal(
    request: ApproveRequest,
    x_tenant_id: str = Header(..., alias="X-Tenant-ID"),
    assist_service: AssistService = Depends(get_assist_service),
):
    """
    제안 승인 또는 거절

    Args:
        request: 승인 요청 (proposal_id, action 등)
        x_tenant_id: 테넌트 ID

    Returns:
        승인된 경우: field_updates, final_response
        거절된 경우: reason
    """
    try:
        result = await assist_service.approve(
            tenant_id=x_tenant_id,
            request=request,
        )
        return ApproveResponse(**result)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"승인 오류: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.post("/refine", response_model=RefineResponse)
async def refine_proposal(
    request: RefineRequest,
    x_tenant_id: str = Header(..., alias="X-Tenant-ID"),
    assist_service: AssistService = Depends(get_assist_service),
):
    """
    제안 수정 요청

    Args:
        request: 수정 요청 (proposal_id, refinement_request 등)
        x_tenant_id: 테넌트 ID

    Returns:
        새로운 버전의 제안
    """
    try:
        result = await assist_service.refine(
            tenant_id=x_tenant_id,
            request=request,
        )
        return RefineResponse(**result)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"수정 오류: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.get("/status/{proposal_id}")
async def get_proposal_status(
    proposal_id: str,
    x_tenant_id: str = Header(..., alias="X-Tenant-ID"),
    assist_service: AssistService = Depends(get_assist_service),
):
    """
    제안 상태 조회

    Args:
        proposal_id: 제안 ID
        x_tenant_id: 테넌트 ID

    Returns:
        제안 상세 정보
    """
    try:
        proposal = await assist_service.get_proposal(
            tenant_id=x_tenant_id,
            proposal_id=proposal_id,
        )
        if not proposal:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"제안을 찾을 수 없습니다: {proposal_id}",
            )
        return proposal

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"상태 조회 오류: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )
