from __future__ import annotations

from app.observability.logging import logger
from app.orchestrator.state import SupportState

# ============================================================
# SAFETY LIMIT
# ============================================================

MAX_ITERATIONS = 2


# ============================================================
# PLAN ROUTER
# ============================================================

def route_after_plan(state: SupportState) -> str:
    """
    PLAN → INTENT

    Errors terminate the workflow.
    """

    logger.info(
        "ROUTER: PLAN | errors=%s",
        bool(state.get("errors")),
    )

    if state.get("errors"):
        logger.warning(
            "ROUTER: PLAN encountered errors"
        )
        return "complete"

    return "intent"


# ============================================================
# INTENT ROUTER
# ============================================================

def route_after_intent(state: SupportState) -> str:
    """
    INTENT → ACT

    If clarification is required, the current workflow
    terminates and returns the clarification response.
    """

    logger.info(
        "ROUTER: INTENT | intent=%s | clarification=%s | errors=%s",
        state.get("intent"),
        state.get("requires_clarification"),
        bool(state.get("errors")),
    )

    if state.get("errors"):
        return "complete"

    if state.get("requires_clarification", False):
        return "complete"

    return "act"


# ============================================================
# CHECK ROUTER
# ============================================================

def route_after_check(state: SupportState) -> str:
    """
    CHECK always proceeds to REFLECT.

    REFLECT is the central decision point.
    """

    logger.info(
        "ROUTER: CHECK | errors=%s",
        bool(state.get("errors")),
    )

    return "reflect"


# ============================================================
# REFLECT ROUTER
# ============================================================

def route_after_reflect(state: SupportState) -> str:
    """
    REFLECT is the central decision point.

    Possible paths:

        REFLECT → REPLAN
        REFLECT → RESOLVE

    Maximum iterations prevent an infinite replan loop.
    """

    iteration = state.get("iteration", 0)

    replan_required = state.get(
        "replan_required",
        False,
    )

    sufficient_evidence = state.get(
        "sufficient_evidence",
        False,
    )

    logger.info(
        "ROUTER: REFLECT | "
        "iteration=%s/%s | "
        "replan_required=%s | "
        "sufficient_evidence=%s | "
        "errors=%s",
        iteration,
        MAX_ITERATIONS,
        replan_required,
        sufficient_evidence,
        bool(state.get("errors")),
    )

    # --------------------------------------------------------
    # Errors
    # --------------------------------------------------------

    if state.get("errors"):
        logger.warning(
            "ROUTER: REFLECT encountered errors, "
            "routing to RESOLVE"
        )

        return "resolve"

    # --------------------------------------------------------
    # Evidence is sufficient
    # --------------------------------------------------------

    if sufficient_evidence and not replan_required:
        logger.info(
            "ROUTER: Evidence sufficient, "
            "routing to RESOLVE"
        )

        return "resolve"

    # --------------------------------------------------------
    # Maximum iterations reached
    # --------------------------------------------------------

    if iteration >= MAX_ITERATIONS:
        logger.warning(
            "ROUTER: Maximum iterations reached "
            "(%s), routing to RESOLVE",
            MAX_ITERATIONS,
        )

        return "resolve"

    # --------------------------------------------------------
    # Replanning required
    # --------------------------------------------------------

    if replan_required or not sufficient_evidence:
        logger.info(
            "ROUTER: Evidence insufficient, "
            "routing to REPLAN"
        )

        return "replan"

    # --------------------------------------------------------
    # Safe fallback
    # --------------------------------------------------------

    logger.info(
        "ROUTER: Defaulting to RESOLVE"
    )

    return "resolve"


# ============================================================
# REPLAN ROUTER
# ============================================================

def route_after_replan(state: SupportState) -> str:
    """
    REPLAN → PLAN

    After replanning, the workflow starts the investigation
    cycle again:

        REPLAN
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
    """

    if state.get("errors"):
        logger.warning(
            "ROUTER: REPLAN encountered errors"
        )
        return "resolve"

    iteration = state.get(
        "iteration",
        0,
    )

    if iteration >= MAX_ITERATIONS:
        logger.warning(
            "ROUTER: Maximum iterations reached "
            "after REPLAN"
        )
        return "resolve"

    logger.info(
        "ROUTER: REPLAN completed | "
        "iteration=%s/%s | routing to PLAN",
        iteration,
        MAX_ITERATIONS,
    )

    return "plan"


# ============================================================
# RESOLVE ROUTER
# ============================================================

def route_after_resolve(state: SupportState) -> str:
    """
    RESOLVE → SEVERITY
    """

    logger.info(
        "ROUTER: RESOLVE | errors=%s",
        bool(state.get("errors")),
    )

    if state.get("errors"):
        return "complete"

    return "severity"


# ============================================================
# SEVERITY ROUTER
# ============================================================

def route_after_severity(state: SupportState) -> str:
    """
    Decide whether human escalation is required.

        Low / Medium → END
        High / Critical → ESCALATION
        Explicit escalation → ESCALATION
    """

    severity = state.get("severity")

    escalation_required = state.get(
        "escalation_required",
        False,
    )

    logger.info(
        "ROUTER: SEVERITY | "
        "severity=%s | "
        "escalation_required=%s",
        severity,
        escalation_required,
    )

    # Explicit escalation wins.
    if escalation_required:
        return "escalation"

    # High and critical require escalation.
    if severity in {"high", "critical"}:
        return "escalation"

    # Low / medium complete normally.
    return "complete"