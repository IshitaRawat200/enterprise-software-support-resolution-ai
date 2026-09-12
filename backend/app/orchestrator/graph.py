from __future__ import annotations

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.graph import END, START, StateGraph

from app.orchestrator.nodes.act_node import act_node
from app.orchestrator.nodes.check_node import check_node
from app.orchestrator.nodes.conversation_node import (
    conversation_node,
    is_simple_conversation,
)
from app.orchestrator.nodes.escalation_node import (
    escalation_node,
)
from app.orchestrator.nodes.intent_node import intent_node
from app.orchestrator.nodes.plan_node import plan_node
from app.orchestrator.nodes.reflect_node import reflect_node
from app.orchestrator.nodes.replan_node import replan_node
from app.orchestrator.nodes.resolve_node import resolve_node
from app.orchestrator.nodes.severity_node import severity_node
from app.orchestrator.routing import (
    route_after_check,
    route_after_reflect,
    route_after_resolve,
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

builder.add_node(
    "plan",
    plan_node,
)

builder.add_node(
    "intent",
    intent_node,
)

builder.add_node(
    "conversation",
    conversation_node,
)

builder.add_node(
    "act",
    act_node,
)

builder.add_node(
    "check",
    check_node,
)

builder.add_node(
    "reflect",
    reflect_node,
)

builder.add_node(
    "replan",
    replan_node,
)

builder.add_node(
    "resolve",
    resolve_node,
)

builder.add_node(
    "severity",
    severity_node,
)

builder.add_node(
    "escalation",
    escalation_node,
)


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


# ============================================================
# INTENT → CONVERSATION / NORMAL WORKFLOW
# ============================================================


def route_after_intent(
    state: SupportState,
) -> str:
    """
    Decide whether the customer message should use the
    conversational fast path or continue through the
    full support investigation workflow.

    Simple greetings bypass:

        ACT
        CHECK
        REFLECT
        REPLAN
        RESOLVE
        SEVERITY

    All actual support issues continue through the
    normal workflow.
    """

    message = (state.get("message") or "").strip()

    if state.get("intent") == "human_handoff":
        return "severity"

    if state.get("human_handoff_required") or state.get("escalation_required"):
        return "severity"

    if is_simple_conversation(message):
        return "conversation"

    return "act"


builder.add_conditional_edges(
    "intent",
    route_after_intent,
    {
        "conversation": "conversation",
        "severity": "severity",
        "act": "act",
    },
)


# ============================================================
# CONVERSATION FAST PATH
# ============================================================

builder.add_edge(
    "conversation",
    END,
)


# ============================================================
# NORMAL SUPPORT WORKFLOW
# ============================================================

builder.add_edge(
    "act",
    "check",
)

builder.add_conditional_edges(
    "check",
    route_after_check,
    {
        "resolve": "resolve",
        "reflect": "reflect",
    },
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
# RESOLVE → SEVERITY / COMPLETE
# ============================================================

builder.add_conditional_edges(
    "resolve",
    route_after_resolve,
    {
        "complete": END,
        "severity": "severity",
    },
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
    Compile the production support graph with the supplied
    PostgreSQL LangGraph checkpointer.
    """

    return builder.compile(
        checkpointer=checkpointer,
    )


def build_uncheckpointed_graph():
    """
    Build a graph without persistence.

    Useful for unit tests and graph visualization.
    """

    return builder.compile()
