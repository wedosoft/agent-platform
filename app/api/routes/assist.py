"""
AI Assistant API 라우트

FDK Custom App에서 호출하는 티켓 분석, 승인, 수정 엔드포인트
SSE 스트리밍을 통한 실시간 진행 상황 업데이트 지원

Streaming Architecture:
- /analyze/stream: SSE endpoint for real-time progressive rendering
- Events: started, searching, analyzing, field_proposal, draft_response, complete, error
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from typing import Any, AsyncGenerator, Dict, Optional, List

from fastapi import APIRouter, Depends, Header, HTTPException, status, BackgroundTasks
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
from app.agents.retriever import retrieve_context
from app.agents.analyzer import analyze_ticket as analyze_ticket_agent
from app.agents.synthesizer import synthesize_results
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


async def process_analysis_background(
    initial_state: Dict[str, Any],
    repo: ProposalRepository,
    tenant_id: str,
    ticket_id: str,
    proposal_id: str
):
    """Background task for analysis"""
    try:
        logger.info(f"Starting background analysis for proposal {proposal_id}")
        final_state = await agent_graph.ainvoke(initial_state)
        
        # Extract results
        proposal_data = final_state.get("proposed_action", {})
        analysis = final_state.get("analysis_result", {})
        search = final_state.get("search_results", {})
        
        # Update proposal with results
        proposal_data["id"] = proposal_id
        proposal_data["tenantId"] = tenant_id
        proposal_data["ticketId"] = ticket_id
        proposal_data["status"] = "draft" # Completed
        
        # Merge analysis/search into proposal if needed or just save as is
        # The Proposal model has fields for these? No, but we can store them in the repo
        # Actually, Proposal model has similar_cases etc.
        
        # Ensure we have a valid Proposal object structure
        # We need to map the dict to the model fields if they differ, but they should match mostly
        
        # Save completed proposal
        await repo.save_proposal(proposal_id, proposal_data)
        logger.info(f"Background analysis completed for proposal {proposal_id}")
        
    except Exception as e:
        logger.error(f"Background analysis failed: {e}")
        # Update status to error
        error_proposal = {
            "id": proposal_id,
            "tenantId": tenant_id,
            "ticketId": ticket_id,
            "status": "error",
            "rejectionReason": str(e)
        }
        await repo.save_proposal(proposal_id, error_proposal)


# =============================================================================
# Routes
# =============================================================================

@router.post("/analyze")
async def analyze_ticket(
    request: AnalyzeRequest,
    background_tasks: BackgroundTasks,
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

    if request.async_mode:
        # Create a placeholder proposal
        proposal_id = str(uuid.uuid4())
        initial_proposal = Proposal(
            id=proposal_id,
            tenantId=x_tenant_id,
            ticketId=request.ticket_id,
            status="processing",
            draftResponse="" # Optional now
        )
        await repo.save_proposal(proposal_id, initial_proposal.model_dump(by_alias=True))
        
        # Start background task
        background_tasks.add_task(
            process_analysis_background,
            initial_state,
            repo,
            x_tenant_id,
            request.ticket_id,
            proposal_id
        )
        
        return AnalyzeResponse(proposal=initial_proposal)

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


# =============================================================================
# Progressive SSE Streaming (New Implementation)
# =============================================================================

async def run_progressive_stream(
    initial_state: Dict[str, Any],
    repo: ProposalRepository,
    tenant_id: str,
    ticket_id: str
) -> AsyncGenerator[Dict[str, Any], None]:
    """
    Progressive SSE streaming with individual field proposals.

    Event flow:
    1. started (proposal_id)
    2. searching (progress)
    3. search_result (if available)
    4. analyzing (progress)
    5. field_proposal (per field, streamed individually)
    6. draft_response (chunked or full)
    7. complete (full proposal)
    """
    proposal_id = str(uuid.uuid4())

    try:
        # 1. Started event
        yield {
            "type": "started",
            "data": {"proposalId": proposal_id, "ticketId": ticket_id}
        }

        state = initial_state.copy()

        # 2. Parallel execution: retrieve + analyze
        # But we stream events as they complete

        # Create tasks for parallel execution
        retrieve_task = asyncio.create_task(retrieve_context(state.copy()))
        analyze_task = asyncio.create_task(analyze_ticket_agent(state.copy()))

        # Yield searching status
        yield {
            "type": "searching",
            "data": {"message": "관련 문서 검색 중..."}
        }

        # Wait for retrieve to complete first (usually faster when skipped)
        retrieve_result = await retrieve_task

        # Yield search results
        search_results = retrieve_result.get("search_results", {})
        state["search_results"] = search_results
        state["metadata"] = retrieve_result.get("metadata", {})

        yield {
            "type": "search_result",
            "data": {
                "similarCases": search_results.get("similar_cases", []),
                "kbArticles": search_results.get("kb_procedures", []),
                "totalResults": search_results.get("total_results", 0)
            }
        }

        # Yield analyzing status
        yield {
            "type": "analyzing",
            "data": {"message": "티켓 분석 중..."}
        }

        # Wait for analyze to complete
        analyze_result = await analyze_task
        analysis = analyze_result.get("analysis_result", {})
        state["analysis_result"] = analysis

        # 3. Stream field proposals individually
        field_proposals = analysis.get("field_proposals", [])
        for proposal in field_proposals:
            yield {
                "type": "field_proposal",
                "data": {
                    "fieldName": proposal.get("field_name"),
                    "fieldLabel": proposal.get("field_label"),
                    "proposedValue": proposal.get("proposed_value"),
                    "reason": proposal.get("reason")
                }
            }
            # Small delay for visual effect (optional)
            await asyncio.sleep(0.1)

        # 4. Synthesize final proposal
        yield {
            "type": "synthesizing",
            "data": {"message": "응답 생성 중..."}
        }

        synthesized = await synthesize_results(state)
        proposal_data = synthesized.get("proposed_action", {})

        # 5. Stream draft response
        draft_response = proposal_data.get("draft_response", "")
        if draft_response:
            yield {
                "type": "draft_response",
                "data": {"text": draft_response}
            }

        # 6. Finalize and save proposal
        proposal_data["id"] = proposal_id
        proposal_data["tenantId"] = tenant_id
        proposal_data["ticketId"] = ticket_id
        proposal_data["status"] = "draft"

        await repo.save_proposal(proposal_id, proposal_data)

        # 7. Complete event with full proposal
        yield {
            "type": "complete",
            "data": {
                "proposal": proposal_data,
                "analysis": analysis,
                "search": search_results
            }
        }

    except Exception as e:
        logger.error(f"Progressive stream failed: {e}", exc_info=True)
        yield {
            "type": "error",
            "data": {
                "message": str(e),
                "proposalId": proposal_id,
                "recoverable": False
            }
        }


@router.post("/analyze/stream")
async def analyze_ticket_stream(
    request: AnalyzeRequest,
    x_tenant_id: str = Header(..., alias="X-Tenant-ID"),
    x_freshdesk_domain: Optional[str] = Header(None, alias="X-Freshdesk-Domain"),
    x_freshdesk_api_key: Optional[str] = Header(None, alias="X-Freshdesk-API-Key"),
    repo: ProposalRepository = Depends(get_proposal_repository)
):
    """
    티켓 분석 SSE 스트리밍 엔드포인트

    실시간으로 분석 진행 상황과 필드 제안을 스트리밍합니다.
    각 필드 제안이 도착하는 대로 프론트엔드에서 즉시 렌더링할 수 있습니다.
    """
    logger.info(f"Stream analyze request for ticket {request.ticket_id} (Tenant: {x_tenant_id})")

    initial_state = {
        "ticket_context": request.model_dump(by_alias=True),
        "tenant_config": {
            "tenant_id": x_tenant_id,
            "domain": x_freshdesk_domain,
            "api_key": x_freshdesk_api_key
        }
    }

    return StreamingResponse(
        sse_generator(run_progressive_stream(initial_state, repo, x_tenant_id, request.ticket_id)),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"  # Disable nginx buffering
        }
    )

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
