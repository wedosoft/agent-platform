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
import uuid
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
from app.agents.orchestrator import build_graph
from app.repositories.proposal_repository import ProposalRepository, get_proposal_repository

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/assist", tags=["assist"])

# Initialize Graph
agent_graph = build_graph()

# =============================================================================
# SSE Streaming Helper
# =============================================================================

async def sse_generator(
    events: AsyncGenerator[Dict[str, Any], None]
) -> AsyncGenerator[str, None]:
    """
    이벤트 스트림을 SSE 포맷으로 변환
    """
    last_heartbeat = time.time()

    try:
        async for event in events:
            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

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
    repo: ProposalRepository = Depends(get_proposal_repository)
):
    """
    티켓 분석 및 AI 제안 생성 (LangGraph 기반)
    """
    logger.info(f"Analyze request for ticket {request.ticket_id} (Tenant: {x_tenant_id})")

    # Initial State
    initial_state = {
        "ticket_context": request.model_dump(by_alias=True),
        "tenant_config": {
            "tenant_id": x_tenant_id,
            "domain": x_freshdesk_domain,
            "api_key": x_freshdesk_api_key
        }
    }

    # --- TEMPORARY: Immediate Mock Response to bypass FDK Timeout ---
    logger.info("Returning IMMEDIATE MOCK response for testing")
    mock_proposal = Proposal(
        id=str(uuid.uuid4()),
        tenantId=x_tenant_id,
        ticketId=request.ticket_id,
        summary="[MOCK] 티켓 분석 테스트 (타임아웃 회피)",
        intent="technical_issue",
        sentiment="neutral",
        draftResponse="안녕하세요. 이것은 타임아웃 문제를 확인하기 위한 테스트 응답입니다. 백엔드 연결은 정상입니다.",
        fieldUpdates={"priority": 3, "status": 2},
        reasoning="테스트 목적의 가상 제안입니다.",
        status="approved"
    )
    return AnalyzeResponse(
        proposal=mock_proposal
    )
    # --------------------------------------------------------------

    if request.stream_progress:
        return StreamingResponse(
            sse_generator(run_agent_stream(initial_state, repo, x_tenant_id, request.ticket_id)),
            media_type="text/event-stream"
        )
    else:
        # Sync execution
        final_state = await agent_graph.ainvoke(initial_state)
        response = await build_analyze_response(final_state, repo, x_tenant_id, request.ticket_id)
        return response

async def run_agent_stream(
    initial_state: Dict[str, Any], 
    repo: ProposalRepository,
    tenant_id: str,
    ticket_id: str
) -> AsyncGenerator[Dict[str, Any], None]:
    """Run LangGraph and yield SSE events"""
    try:
        final_state = {}
        async for event in agent_graph.astream(initial_state):
            for node_name, state_update in event.items():
                final_state.update(state_update) # Keep track of state
                
                yield {
                    "type": "progress",
                    "data": {
                        "stage": node_name,
                        "message": f"Completed {node_name}..."
                    }
                }
                
                if node_name == "retrieve" and "search_results" in state_update:
                    yield {
                        "type": "search_results",
                        "data": state_update["search_results"]
                    }
                elif node_name == "analyze" and "analysis_result" in state_update:
                    yield {
                        "type": "analysis_result",
                        "data": state_update["analysis_result"]
                    }
                elif node_name == "resolve" and "proposed_action" in state_update:
                    # Save proposal before yielding
                    proposal_data = state_update["proposed_action"]
                    proposal_id = str(uuid.uuid4())
                    proposal_data["id"] = proposal_id
                    proposal_data["tenantId"] = tenant_id
                    proposal_data["ticketId"] = ticket_id
                    
                    await repo.save_proposal(proposal_id, proposal_data)
                    
                    yield {
                        "type": "proposal",
                        "data": proposal_data
                    }

        yield {"type": "complete", "data": {"status": "done"}}

    except Exception as e:
        logger.error(f"Agent execution failed: {e}")
        yield {"type": "error", "message": str(e)}

async def build_analyze_response(
    state: Dict[str, Any],
    repo: ProposalRepository,
    tenant_id: str,
    ticket_id: str
) -> Dict[str, Any]:
    """Build JSON response from final state"""
    proposal = state.get("proposed_action", {})
    analysis = state.get("analysis_result", {})
    search = state.get("search_results", {})
    
    if proposal:
        proposal_id = str(uuid.uuid4())
        proposal["id"] = proposal_id
        proposal["tenantId"] = tenant_id
        proposal["ticketId"] = ticket_id
        await repo.save_proposal(proposal_id, proposal)
    
    return {
        "proposal": proposal,
        "analysis": analysis,
        "search": search
    }

@router.post("/approve", response_model=ApproveResponse)
async def approve_proposal(
    request: ApproveRequest,
    x_tenant_id: str = Header(..., alias="X-Tenant-ID"),
    repo: ProposalRepository = Depends(get_proposal_repository),
):
    """
    제안 승인 또는 거절
    """
    try:
        proposal = await repo.get_proposal(request.proposal_id)
        if not proposal:
            raise HTTPException(status_code=404, detail="Proposal not found")
            
        # Logic to handle approval (e.g., update Freshdesk, log to Supabase)
        # For MVP, we just return success
        
        status_str = "approved" if request.action == "approve" else "rejected"
        
        return ApproveResponse(
            status=status_str,
            field_updates=proposal.get("field_updates"),
            final_response=request.final_response or proposal.get("draft_response"),
            reason=request.rejection_reason
        )

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
    repo: ProposalRepository = Depends(get_proposal_repository),
):
    """
    제안 수정 요청
    """
    try:
        proposal = await repo.get_proposal(request.proposal_id)
        if not proposal:
            raise HTTPException(status_code=404, detail="Proposal not found")
            
        # Logic to refine proposal using LLM (not implemented in this MVP step)
        # We would call the Resolver agent again with feedback
        
        # Create a new proposal object based on the old one but with incremented version
        new_version = proposal.get("proposal_version", 1) + 1
        
        refined_proposal = Proposal(
            id=request.proposal_id,
            tenantId=x_tenant_id,
            ticketId=request.ticket_id,
            proposalVersion=new_version,
            draftResponse=proposal.get("draft_response") or "", # In real logic, this would be refined
            fieldUpdates=proposal.get("field_updates"),
            reasoning="Refinement placeholder"
        )
        
        return RefineResponse(
            proposal=refined_proposal,
            version=new_version
        )

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
    repo: ProposalRepository = Depends(get_proposal_repository),
):
    """
    제안 상태 조회
    """
    try:
        proposal = await repo.get_proposal(proposal_id)
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
