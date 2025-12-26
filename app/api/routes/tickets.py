"""
Ticket Analysis API Routes

POST /api/tickets/{ticket_id}/analyze - Schema-validated ticket analysis
GET /api/tickets/{ticket_id}/analyses - Get analysis history for a ticket

This module provides the new structured analysis API that replaces the
chat-based approach with schema-validated JSON input/output.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Header, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.services.orchestrator import (
    AnalysisOptions as OrchestratorOptions,
    get_ticket_analysis_orchestrator,
)
from app.services.orchestrator.persistence import get_analysis_persistence
from app.utils.schema_validation import validate_or_raise, validate_output

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/tickets", tags=["tickets"])


# =============================================================================
# Request/Response Models
# =============================================================================


class TicketConversation(BaseModel):
    """Single conversation entry."""

    id: Optional[int] = None
    body: Optional[str] = None
    body_text: Optional[str] = None
    incoming: Optional[bool] = None
    private: Optional[bool] = None
    source: Optional[int] = None
    user_id: Optional[int] = None
    created_at: Optional[str] = None


class TicketField(BaseModel):
    """Ticket field definition."""

    id: Optional[int] = None
    name: Optional[str] = None
    label: Optional[str] = None
    label_for_customers: Optional[str] = None
    type: Optional[str] = None
    choices: Optional[Any] = None
    required_for_customers: Optional[bool] = None
    required_for_agents: Optional[bool] = None


class AnalyzeOptions(BaseModel):
    """Optional analysis configuration."""

    skip_retrieval: bool = False
    include_evidence: bool = True
    confidence_threshold: float = 0.7
    selected_fields: Optional[List[str]] = None
    response_tone: str = "formal"


class TicketAnalyzeRequest(BaseModel):
    """Request body for ticket analysis."""

    subject: Optional[str] = None
    description: Optional[str] = None
    description_text: Optional[str] = None
    priority: Optional[int] = None
    status: Optional[int] = None
    source: Optional[int] = None
    type: Optional[str] = None
    tags: Optional[List[str]] = None
    requester_id: Optional[int] = None
    responder_id: Optional[int] = None
    group_id: Optional[int] = None
    custom_fields: Optional[Dict[str, Any]] = None
    conversations: Optional[List[TicketConversation]] = None
    ticket_fields: Optional[List[TicketField]] = Field(
        default=None, alias="ticketFields"
    )
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    # Options embedded in request body
    options: Optional[AnalyzeOptions] = None

    class Config:
        populate_by_name = True


# =============================================================================
# API Endpoints
# =============================================================================


@router.post("/{ticket_id}/analyze")
async def analyze_ticket(
    ticket_id: str,
    request: TicketAnalyzeRequest,
    x_tenant_id: str = Header(..., alias="X-Tenant-ID"),
    x_freshdesk_domain: Optional[str] = Header(None, alias="X-Freshdesk-Domain"),
    x_freshdesk_api_key: Optional[str] = Header(None, alias="X-Freshdesk-API-Key"),
) -> Dict[str, Any]:
    """
    Analyze a ticket and return structured analysis with gate decision.

    This endpoint performs schema-validated ticket analysis:
    1. Validates input against ticket_normalized_v1 schema
    2. Runs analysis pipeline via orchestrator
    3. Validates output against ticket_analysis_v1 schema
    4. Returns structured analysis with gate decision

    Args:
        ticket_id: Unique identifier for the ticket
        request: Ticket data for analysis
        x_tenant_id: Tenant identifier (required)
        x_freshdesk_domain: Freshdesk domain (optional)
        x_freshdesk_api_key: Freshdesk API key (optional)

    Returns:
        Structured analysis response with:
        - analysis_id: UUID for this analysis run
        - ticket_id: The analyzed ticket ID
        - status: completed | failed | partial
        - gate: CONFIRM | EDIT | DECIDE | TEACH
        - analysis: narrative, root_cause, resolution, field_proposals, evidence
        - meta: timing, model info, prompt version

    Raises:
        400 INVALID_INPUT_SCHEMA: Input validation failed
        500 ANALYSIS_FAILED: Orchestrator/LLM failure
    """
    logger.info(f"[tickets.analyze] ticket_id={ticket_id}, tenant_id={x_tenant_id}")

    # Build normalized input (exclude options field)
    request_dict = request.model_dump(
        exclude_none=True, by_alias=False, exclude={"options"}
    )
    normalized_input = {"ticket_id": ticket_id, **request_dict}

    # Extract options
    req_options = request.options or AnalyzeOptions()

    # Validate input against schema
    validate_or_raise("ticket_normalized_v1", normalized_input)

    try:
        # Convert to orchestrator options
        orchestrator_options = OrchestratorOptions(
            skip_retrieval=req_options.skip_retrieval,
            include_evidence=req_options.include_evidence,
            confidence_threshold=req_options.confidence_threshold,
            selected_fields=req_options.selected_fields,
            response_tone=req_options.response_tone,
        )

        # Call orchestrator
        orchestrator = get_ticket_analysis_orchestrator()
        result = await orchestrator.run_ticket_analysis(
            normalized_input=normalized_input,
            options=orchestrator_options,
            tenant_id=x_tenant_id,
        )

        # Build response
        response = {
            "analysis_id": result.analysis_id,
            "ticket_id": ticket_id,
            "status": "completed" if result.success else "failed",
            "gate": result.gate,
            "analysis": result.analysis,
            "meta": result.meta,
        }

        # Validate output against schema
        if not validate_output("ticket_analysis_v1", response):
            logger.error(
                f"[tickets.analyze] Output validation failed for {result.analysis_id}"
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={
                    "error_code": "ANALYSIS_FAILED",
                    "message": "Output validation failed against ticket_analysis_v1 schema",
                },
            )

        # If orchestrator failed, return 500
        if not result.success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={
                    "error_code": "ANALYSIS_FAILED",
                    "message": result.error or "Analysis pipeline failed",
                },
            )

        logger.info(
            f"[tickets.analyze] Success: analysis_id={result.analysis_id}, gate={result.gate}"
        )
        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[tickets.analyze] Unexpected error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "ANALYSIS_FAILED", "message": str(e)},
        )


@router.get("/{ticket_id}/analyses")
async def get_ticket_analyses(
    ticket_id: str,
    limit: int = Query(default=10, ge=1, le=100),
    x_tenant_id: str = Header(..., alias="X-Tenant-ID"),
) -> Dict[str, Any]:
    """
    Get analysis history for a ticket.

    Args:
        ticket_id: Ticket ID to get history for
        limit: Maximum number of records to return (default 10, max 100)
        x_tenant_id: Tenant identifier

    Returns:
        List of past analysis runs for the ticket
    """
    logger.info(f"[tickets.analyses] ticket_id={ticket_id}, tenant_id={x_tenant_id}")

    # Fetch from persistence layer
    persistence = get_analysis_persistence()
    history = await persistence.get_analysis_history(
        tenant_id=x_tenant_id,
        ticket_id=ticket_id,
        limit=limit,
    )

    return {
        "ticket_id": ticket_id,
        "analyses": history,
        "total": len(history),
        "limit": limit,
    }


@router.get("/{ticket_id}/analyses/{analysis_id}")
async def get_analysis_by_id(
    ticket_id: str,
    analysis_id: str,
    x_tenant_id: str = Header(..., alias="X-Tenant-ID"),
) -> Dict[str, Any]:
    """
    Get a specific analysis by ID.

    Args:
        ticket_id: Ticket ID (for validation)
        analysis_id: Analysis UUID
        x_tenant_id: Tenant identifier

    Returns:
        Full analysis record

    Raises:
        404: Analysis not found
    """
    logger.info(
        f"[tickets.analysis] ticket_id={ticket_id}, "
        f"analysis_id={analysis_id}, tenant_id={x_tenant_id}"
    )

    persistence = get_analysis_persistence()
    analysis = await persistence.get_analysis_by_id(
        analysis_id=analysis_id,
        tenant_id=x_tenant_id,
    )

    if analysis is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error_code": "ANALYSIS_NOT_FOUND",
                "message": f"Analysis {analysis_id} not found",
            },
        )

    return analysis
