from __future__ import annotations

from langgraph.graph import (
    END,
    START,
    StateGraph,
)

from app.orchestrator.nodes import (
    act_node,
    check_node,
    intent_node,
    plan_node,
    reflect_node,
)

from app.orchestrator.routing import (
    route_after_check,
    route_after_intent,
    route_after_plan,
    route_after_reflect,
)

from app.orchestrator.state import (
    SupportState,
)


def build_support_graph():
    """
    Build the enterprise support orchestration graph.

    Architecture:

        START
          ↓
        PLAN
          ↓
        INTENT
          ↓
        ACT
          ↓
        CHECK
          ↓
        REFLECT
          │
          ├──────────────→ END
          │
          └── RE-PLAN ──→ PLAN

    Specialized agents are called from ACT
    and other future orchestration phases.
    """

    workflow = StateGraph(
        SupportState
    )

    # ========================================================
    # NODES
    # ========================================================

    workflow.add_node(
        "plan",
        plan_node,
    )

    workflow.add_node(
        "intent",
        intent_node,
    )

    workflow.add_node(
        "act",
        act_node,
    )

    workflow.add_node(
        "check",
        check_node,
    )

    workflow.add_node(
        "reflect",
        reflect_node,
    )

    # ========================================================
    # START → PLAN
    # ========================================================

    workflow.add_edge(
        START,
        "plan",
    )

    # ========================================================
    # PLAN → INTENT
    # ========================================================

    workflow.add_conditional_edges(
        "plan",
        route_after_plan,
        {
            "intent": "intent",
            END: END,
        },
    )

    # ========================================================
    # INTENT → ACT
    # ========================================================

    workflow.add_conditional_edges(
        "intent",
        route_after_intent,
        {
            "act": "act",
            END: END,
        },
    )

    # ========================================================
    # ACT → CHECK
    # ========================================================

    workflow.add_edge(
        "act",
        "check",
    )

    # ========================================================
    # CHECK → REFLECT
    # ========================================================

    workflow.add_conditional_edges(
        "check",
        route_after_check,
        {
            "reflect": "reflect",
        },
    )

    # ========================================================
    # REFLECT → END / RE-PLAN
    # ========================================================

    workflow.add_conditional_edges(
        "reflect",
        route_after_reflect,
        {
            "plan": "plan",
            END: END,
        },
    )

    return workflow.compile()


# ============================================================
# COMPILED GRAPH
# ============================================================

support_graph = build_support_graph()