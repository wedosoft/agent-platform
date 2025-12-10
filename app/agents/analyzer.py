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
        
        analysis_result = await llm_adapter.analyze_ticket(ticket_context)
        
        state["analysis_result"] = analysis_result
        logger.info(f"Analysis complete: {analysis_result.get('intent')}")
        
        return state

    except Exception as e:
        logger.error(f"Analysis failed: {e}")
        if "errors" not in state:
            state["errors"] = []
        state["errors"].append(f"Analysis error: {str(e)}")
        return state
