from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

IntentType = Literal[
    "usage_configuration",
    "integration_api",
    "performance_latency",
    "production_incident",
    "billing_account",
    "unknown",
]


SuggestedRoute = Literal[
    "rag",
    "sql",
    "hybrid",
    "incident",
    "clarification",
]


InitialAction = Literal[
    "retrieve_documentation",
    "validate_account",
    "query_support_data",
    "validate_incident",
    "ask_clarifying_question",
]


class IntentClassificationRequest(BaseModel):
    message: str = Field(
        min_length=1,
        max_length=10000,
    )


class IntentClassificationResult(BaseModel):
    """
    Output of the PLAN-stage Intent Agent.

    This is an initial planning proposal.
    The LangGraph orchestrator makes the final execution decision.
    """

    intent: IntentType

    confidence: float = Field(
        ge=0.0,
        le=1.0,
    )

    reason: str = Field(
        min_length=1,
        max_length=2000,
    )

    requires_clarification: bool = False

    suggested_route: SuggestedRoute

    initial_action: InitialAction

    check_requirements: list[str] = Field(
        default_factory=list,
        max_length=10,
    )
