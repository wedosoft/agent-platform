"""
LangGraph Analyzer Agent
Analyzes ticket intent and sentiment using LLM Adapter
"""
import logging
from app.agents.state import AgentState
from app.services.llm_adapter import LLMAdapter

logger = logging.getLogger(__name__)

async def analyze_ticket(state: AgentState) -> AgentState:
    """
    Analyze ticket intent, sentiment, and summary.
    """
    try:
        logger.info("Analyzing ticket")
        llm_adapter = LLMAdapter()
        
        ticket_context = state.get("ticket_context", {})
        response_tone = state.get("response_tone", "formal")

        fields_only = bool(
            (ticket_context or {}).get("fieldsOnly")
            or state.get("fields_only")
            or state.get("fieldsOnly")
        )

        if fields_only:
            # Field proposals only (fast path)
            analysis_result = await llm_adapter.propose_fields_only(ticket_context, response_tone=response_tone)
        else:
            analysis_result = await llm_adapter.analyze_ticket(ticket_context, response_tone=response_tone)

        proposals = analysis_result.get("field_proposals")
        if isinstance(proposals, list):
            # Always drop "source" proposals (tests/UX contract)
            proposals = [p for p in proposals if p.get("field_name") != "source"]

            # Filter field proposals based on selected_fields
            selected_fields = state.get("selected_fields", [])
            if selected_fields:
                proposals = [p for p in proposals if p.get("field_name") in selected_fields]

            analysis_result["field_proposals"] = proposals
        
        state["analysis_result"] = analysis_result
        logger.info(f"Analysis complete: {analysis_result.get('intent')}")
        
        return state

    except Exception as e:
        logger.error(f"Analysis failed: {e}")
        if "errors" not in state:
            state["errors"] = []
        state["errors"].append(f"Analysis error: {str(e)}")
        return state
