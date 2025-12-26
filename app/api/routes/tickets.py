"""
Ticket Analysis API Routes

POST /api/tickets/{ticket_id}/analyze - Schema-validated ticket analysis
GET /api/tickets/{ticket_id}/analyses - Get analysis history for a ticket

This module provides the new structured analysis API that replaces the
chat-based approach with schema-validated JSON input/output.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field

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
    ticket_fields: Optional[List[TicketField]] = Field(default=None, alias="ticketFields")
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
    2. Runs analysis pipeline (orchestrator in PR2)
    3. Validates output against ticket_analysis_v1 schema
    4. Returns structured analysis with gate decision

    Args:
        ticket_id: Unique identifier for the ticket
        request: Ticket data for analysis
        options: Optional analysis configuration
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
    request_dict = request.model_dump(exclude_none=True, by_alias=False, exclude={"options"})
    normalized_input = {
        "ticket_id": ticket_id,
        **request_dict
    }

    # Extract options for later use
    options = request.options or AnalyzeOptions()

    # Validate input against schema
    validate_or_raise("ticket_normalized_v1", normalized_input)

    try:
        # TODO PR2: Call orchestrator
        # orchestrator = get_ticket_analysis_orchestrator()
        # analysis, gate, meta = await orchestrator.run_ticket_analysis(
        #     normalized_input,
        #     options or AnalyzeOptions(),
        #     x_tenant_id
        # )

        # PR1: Placeholder response (skeleton)
        analysis_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()

        # Compute placeholder gate based on available data
        has_description = bool(request.description or request.description_text)
        has_conversations = bool(request.conversations and len(request.conversations) > 0)
        placeholder_confidence = 0.5 if has_description else 0.2
        if has_conversations:
            placeholder_confidence += 0.3

        # Determine gate
        if placeholder_confidence >= 0.9:
            gate = "CONFIRM"
        elif placeholder_confidence >= 0.7:
            gate = "EDIT"
        elif placeholder_confidence >= 0.5:
            gate = "DECIDE"
        else:
            gate = "TEACH"

        response = {
            "analysis_id": analysis_id,
            "ticket_id": ticket_id,
            "status": "completed",
            "gate": gate,
            "analysis": {
                "narrative": {
                    "summary": f"Ticket {ticket_id} analysis pending orchestrator implementation.",
                    "timeline": []
                },
                "root_cause": None,
                "resolution": [],
                "confidence": placeholder_confidence,
                "open_questions": [
                    "Orchestrator not yet implemented - PR2 required"
                ],
                "risk_tags": [],
                "intent": "unknown",
                "sentiment": "neutral",
                "field_proposals": [],
                "evidence": []
            },
            "meta": {
                "llm_provider": "none",
                "llm_model": "placeholder",
                "prompt_version": "ticket_analysis_cot_v1",
                "latency_ms": 0,
                "token_usage": {"input": 0, "output": 0},
                "retrieval_count": 0,
                "created_at": now
            }
        }

        # Validate output against schema
        if not validate_output("ticket_analysis_v1", response):
            logger.error(f"[tickets.analyze] Output validation failed for {analysis_id}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={
                    "error_code": "ANALYSIS_FAILED",
                    "message": "Output validation failed against ticket_analysis_v1 schema"
                }
            )

        logger.info(f"[tickets.analyze] Success: analysis_id={analysis_id}, gate={gate}")
        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[tickets.analyze] Unexpected error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error_code": "ANALYSIS_FAILED",
                "message": str(e)
            }
        )


@router.get("/{ticket_id}/analyses")
async def get_ticket_analyses(
    ticket_id: str,
    limit: int = 10,
    x_tenant_id: str = Header(..., alias="X-Tenant-ID"),
) -> Dict[str, Any]:
    """
    Get analysis history for a ticket.

    Args:
        ticket_id: Ticket ID to get history for
        limit: Maximum number of records to return (default 10)
        x_tenant_id: Tenant identifier

    Returns:
        List of past analysis runs for the ticket
    """
    logger.info(f"[tickets.analyses] ticket_id={ticket_id}, tenant_id={x_tenant_id}")

    # TODO PR2: Fetch from persistence layer
    # persistence = get_analysis_persistence()
    # history = await persistence.get_analysis_history(x_tenant_id, ticket_id, limit)

    # PR1: Placeholder empty response
    return {
        "ticket_id": ticket_id,
        "analyses": [],
        "total": 0,
        "limit": limit
    }
