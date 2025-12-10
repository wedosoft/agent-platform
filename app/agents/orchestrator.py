"""
LangGraph Orchestrator
Defines the workflow graph
"""
import logging
from typing import Literal
from langgraph.graph import StateGraph, END

from app.agents.state import AgentState
from app.agents.retriever import retrieve_context
from app.agents.analyzer import analyze_ticket
from app.agents.resolver import propose_solution
from app.agents.approval import approval_node, approval_condition

logger = logging.getLogger(__name__)

def build_graph() -> StateGraph:
    """
    Build the LangGraph workflow:
    START -> Retrieve -> Analyze -> Resolve -> Approval -> (End or Loop)
    """
    graph = StateGraph(AgentState)

    # Add Nodes
    graph.add_node("retrieve", retrieve_context)
    graph.add_node("analyze", analyze_ticket)
    graph.add_node("resolve", propose_solution)
    graph.add_node("approval", approval_node)

    # Define Edges
    graph.set_entry_point("retrieve")
    graph.add_edge("retrieve", "analyze")
    graph.add_edge("analyze", "resolve")
    graph.add_edge("resolve", "approval")
    
    # Conditional Edge from Approval
    graph.add_conditional_edges(
        "approval",
        approval_condition,
        {
            "end": END,
            "resolve": "resolve"
        }
    )

    return graph.compile()
