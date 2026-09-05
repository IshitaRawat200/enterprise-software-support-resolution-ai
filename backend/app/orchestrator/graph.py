from __future__ import annotations

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.graph import END, START, StateGraph

from app.orchestrator.nodes.act_node import act_node
from app.orchestrator.nodes.check_node import check_node
from app.orchestrator.nodes.escalation_node import escalation_node
from app.orchestrator.nodes.intent_node import intent_node
from app.orchestrator.nodes.plan_node import plan_node
from app.orchestrator.nodes.reflect_node import reflect_node
from app.orchestrator.nodes.replan_node import replan_node
from app.orchestrator.nodes.resolve_node import resolve_node
from app.orchestrator.nodes.severity_node import severity_node
from app.orchestrator.routing import (
    route_after_reflect,
    route_after_severity,
)
from app.orchestrator.state import SupportState

# ============================================================
# GRAPH BUILDER
# ============================================================

builder = StateGraph(SupportState)


# ============================================================
# NODES
# ============================================================

builder.add_node("plan", plan_node)
builder.add_node("intent", intent_node)
builder.add_node("act", act_node)
builder.add_node("check", check_node)
builder.add_node("reflect", reflect_node)
builder.add_node("replan", replan_node)
builder.add_node("resolve", resolve_node)
builder.add_node("severity", severity_node)
builder.add_node("escalation", escalation_node)


# ============================================================
# INITIAL FLOW
# ============================================================

builder.add_edge(
    START,
    "plan",
)

builder.add_edge(
    "plan",
    "intent",
)

builder.add_edge(
    "intent",
    "act",
)

builder.add_edge(
    "act",
    "check",
)

builder.add_edge(
    "check",
    "reflect",
)


# ============================================================
# REFLECT DECISION
# ============================================================

builder.add_conditional_edges(
    "reflect",
    route_after_reflect,
    {
        "replan": "replan",
        "resolve": "resolve",
    },
)


# ============================================================
# REPLAN → PLAN
# ============================================================

builder.add_edge(
    "replan",
    "plan",
)


# ============================================================
# RESOLVE → SEVERITY
# ============================================================

builder.add_edge(
    "resolve",
    "severity",
)


# ============================================================
# SEVERITY DECISION
# ============================================================

builder.add_conditional_edges(
    "severity",
    route_after_severity,
    {
        "escalation": "escalation",
        "complete": END,
    },
)


# ============================================================
# ESCALATION → END
# ============================================================

builder.add_edge(
    "escalation",
    END,
)


# ============================================================
# BUILD COMPILED GRAPH
# ============================================================

def build_support_graph(
    checkpointer: AsyncPostgresSaver,
):
    """
    Compile the support graph with the supplied LangGraph
    checkpointer.
    """

    return builder.compile(
        checkpointer=checkpointer,
    )

def build_uncheckpointed_graph():
    """
    Build a graph for visualization/testing where persistence
    is not required.
    """
    return builder.compile()