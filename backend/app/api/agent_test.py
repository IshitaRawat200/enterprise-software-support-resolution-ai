from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.agents.intent.intent_schema import (
    IntentClassificationResult,
)
from app.agents.retrieval.retrieval_agent import (
    RetrievalAgent,
)
from app.agents.retrieval.retrieval_schema import (
    RetrievalResult,
)
from app.services.intent_service import IntentService

router = APIRouter(
    prefix="/agent-test",
    tags=["Agent Testing"],
)


# ============================================================
# INTENT AGENT TEST
# ============================================================


class IntentAgentTestRequest(BaseModel):
    message: str = Field(
        min_length=1,
        max_length=10000,
    )


@router.post(
    "/intent",
    response_model=IntentClassificationResult,
)
async def test_intent_agent(
    request: IntentAgentTestRequest,
) -> IntentClassificationResult:

    intent_service = IntentService()

    result = await intent_service.classify(request.message)

    return result


# ============================================================
# RETRIEVAL AGENT TEST
# ============================================================


class RetrievalAgentTestRequest(BaseModel):
    query: str = Field(
        min_length=1,
        max_length=10000,
    )

    intent: str | None = Field(
        default=None,
        max_length=100,
    )

    intent_confidence: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
    )


@router.post(
    "/retrieval",
    response_model=RetrievalResult,
)
async def test_retrieval_agent(
    request: RetrievalAgentTestRequest,
) -> RetrievalResult:

    retrieval_agent = RetrievalAgent()

    result = await retrieval_agent.run(
        query=request.query,
    )

    return result
