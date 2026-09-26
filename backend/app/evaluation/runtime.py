from __future__ import annotations

import asyncio

from app.evaluation.production_evaluator import ProductionEvaluator
from app.evaluation.ragas_evaluator import RagasEvaluator

_evaluator: ProductionEvaluator | None = None
_evaluator_lock = asyncio.Lock()


async def get_production_evaluator() -> ProductionEvaluator:
    """Create one evaluator per application process (async-safe)."""

    global _evaluator

    if _evaluator is not None:
        return _evaluator

    async with _evaluator_lock:
        if _evaluator is None:
            _evaluator = ProductionEvaluator(ragas_evaluator=RagasEvaluator())

    return _evaluator
