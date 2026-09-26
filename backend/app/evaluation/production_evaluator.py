from __future__ import annotations

import logging
from typing import Any

from app.evaluation.ragas_evaluator import RagasEvaluator

logger = logging.getLogger("enterprise_support_ai")


class ProductionEvaluator:
    """Production evaluation orchestration."""

    def __init__(self, *, ragas_evaluator: RagasEvaluator) -> None:
        self.ragas_evaluator = ragas_evaluator
        logger.info("Production evaluator initialized with RAGAS evaluator")

    async def evaluate_rag_request(
        self,
        *,
        question: str,
        answer: str,
        retrieval_results: Any,
        reference: str | None = None,
        request_id: str = "unknown",
    ) -> dict[str, Any]:
        retrieval_count = len(retrieval_results) if retrieval_results is not None else 0

        logger.info(
            "Production evaluation starting request_id=%s retrieval_results=%s reference_present=%s",
            request_id,
            retrieval_count,
            reference is not None,
        )

        try:
            result = await self.ragas_evaluator.evaluate_rag_request(
                question=question,
                answer=answer,
                retrieval_results=retrieval_results,
                reference=reference,
                request_id=request_id,
            )
        except Exception as exc:
            logger.exception(
                "Production evaluation failed request_id=%s error=%s",
                request_id,
                exc,
            )
            return {
                "request_id": request_id,
                "faithfulness": None,
                "answer_relevance": None,
                "context_precision": None,
                "context_recall": None,
                "ragas_evaluated": False,
                "ragas_errors": [f"{type(exc).__name__}: {exc}"],
            }

        result["request_id"] = request_id
        logger.info(
            "Production evaluation completed request_id=%s faithfulness=%s answer_relevance=%s context_precision=%s context_recall=%s ragas_evaluated=%s",
            request_id,
            result.get("faithfulness"),
            result.get("answer_relevance"),
            result.get("context_precision"),
            result.get("context_recall"),
            result.get("ragas_evaluated"),
        )
        return result