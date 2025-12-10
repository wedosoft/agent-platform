"""
LangGraph Resolver Agent
Generates draft response and field updates using LLM Adapter
"""
import logging
from app.agents.state import AgentState
from app.services.llm_adapter import LLMAdapter

logger = logging.getLogger(__name__)

async def propose_solution(state: AgentState) -> AgentState:
    """
    Generate draft response and field updates.
    """
    try:
        logger.info("Proposing solution")
        llm_adapter = LLMAdapter()
        
        ticket_context = state.get("ticket_context", {})
        search_results = state.get("search_results", {})
        analysis_result = state.get("analysis_result", {})
        
        # If Gemini already provided a good answer, we can include it in the context
        if "gemini_response" in search_results:
            analysis_result["gemini_suggestion"] = search_results["gemini_response"]

        proposal = await llm_adapter.propose_solution(
            ticket_context,
            search_results,
            analysis_result
        )
        
        state["proposed_action"] = proposal
        logger.info("Solution proposed")
        
        return state

    except Exception as e:
        logger.error(f"Proposal failed: {e}")
        if "errors" not in state:
            state["errors"] = []
        state["errors"].append(f"Proposal error: {str(e)}")
        return state
