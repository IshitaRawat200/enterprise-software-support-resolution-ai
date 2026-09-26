from __future__ import annotations

import json
import re
from typing import Any

from llama_index.llms.groq import Groq

from app.config import get_settings
from app.observability.logging import logger


class ProductionQualityEvaluator:
    """
    Request-level quality evaluator used by the live chat endpoint.

    It evaluates the generated answer against the retrieved evidence and
    returns the metrics required by the ERIS chat UI/workbook.

    These request-level values are observability/evaluation telemetry.
    They do not redefine the six approved production SLOs.
    """

    def __init__(self) -> None:
        settings = get_settings()

        if not settings.groq_api_key:
            raise RuntimeError("GROQ_API_KEY is not configured.")

        self.llm = Groq(
            model=settings.groq_simple_model,
            api_key=settings.groq_api_key,
            temperature=0.0,
        )

    @staticmethod
    def _context_text(
        retrieval_results: list[dict[str, Any]],
    ) -> str:
        parts: list[str] = []

        for index, item in enumerate(retrieval_results, start=1):
            if not isinstance(item, dict):
                continue

            content = (
                item.get("content") or item.get("text") or item.get("source") or ""
            )

            if not content:
                continue

            source = (
                item.get("document_name")
                or item.get("file_name")
                or item.get("source_name")
                or f"evidence_{index}"
            )

            parts.append(f"[Evidence {index} | {source}]\n{str(content).strip()}")

        return "\n\n".join(parts)

    @staticmethod
    def _extract_json(text: str) -> dict[str, Any]:
        cleaned = text.strip()

        if cleaned.startswith("```"):
            cleaned = re.sub(
                r"^```(?:json)?\s*",
                "",
                cleaned,
                flags=re.IGNORECASE,
            )
            cleaned = re.sub(
                r"\s*```$",
                "",
                cleaned,
            )

        try:
            value = json.loads(cleaned)
            if isinstance(value, dict):
                return value
        except json.JSONDecodeError:
            pass

        match = re.search(
            r"\{.*\}",
            cleaned,
            flags=re.DOTALL,
        )

        if match:
            try:
                value = json.loads(match.group(0))
                if isinstance(value, dict):
                    return value
            except json.JSONDecodeError:
                pass

        raise ValueError("Quality evaluator did not return valid JSON.")

    @staticmethod
    def _score(
        value: Any,
    ) -> float | None:
        if value is None:
            return None

        try:
            score = float(value)
        except (TypeError, ValueError):
            return None

        # Accept either 0..1 or 0..100.
        if 0.0 <= score <= 1.0:
            score *= 100.0

        return max(0.0, min(100.0, score))

    @staticmethod
    def _usage_cost_from_raw(raw: Any) -> float | None:
        if raw is None:
            return None

        usage = getattr(raw, "usage", None)
        if usage is None and isinstance(raw, dict):
            usage = raw.get("usage")

        if usage is None:
            return None

        if hasattr(usage, "model_dump"):
            usage = usage.model_dump()
        elif not isinstance(usage, dict):
            try:
                usage = dict(usage)
            except (TypeError, ValueError):
                return None

        model = str(usage.get("model") or "openai/gpt-oss-20b").strip().lower()
        pricing = {
            "openai/gpt-oss-20b": {
                "input": 0.075,
                "output": 0.300,
                "cached_input": 0.037,
            }
        }.get(model)

        if pricing is None:
            return None

        try:
            prompt = max(
                0.0, float(usage.get("prompt_tokens") or usage.get("input_tokens") or 0)
            )
            completion = max(
                0.0,
                float(
                    usage.get("completion_tokens") or usage.get("output_tokens") or 0
                ),
            )
            cached = max(0.0, min(prompt, float(usage.get("cached_tokens") or 0)))
        except (TypeError, ValueError):
            return None

        return round(
            (
                (prompt - cached) * pricing["input"]
                + cached * pricing["cached_input"]
                + completion * pricing["output"]
            )
            / 1_000_000.0,
            8,
        )

    async def evaluate(
        self,
        *,
        question: str,
        answer: str,
        retrieval_results: list[dict[str, Any]] | None = None,
        route: str | None = None,
        expected_route: str | None = None,
        guardrail_allowed: bool | None = None,
    ) -> dict[str, Any]:
        evidence = self._context_text(retrieval_results or [])

        if not evidence:
            logger.info("Production quality evaluation skipped: no retrieved evidence.")
            return {
                "accuracy": None,
                "faithfulness": None,
                "answer_relevance": None,
                "context_precision": None,
                "context_recall": None,
                "route_accuracy": None,
                "guardrail_effectiveness": (
                    100.0
                    if guardrail_allowed is True
                    else 0.0
                    if guardrail_allowed is False
                    else None
                ),
                "quality_evaluation_available": False,
                "quality_evaluation_error": "No retrieved evidence.",
            }

        route_text = route or "unknown"
        expected_route_text = expected_route or "not provided"

        prompt = f"""
You are the production quality evaluator for an enterprise support RAG system.

Evaluate the answer using ONLY the user's question and the retrieved evidence.
Do not use retrieval confidence as a quality score.
Do not invent facts that are not supported by the evidence.

USER QUESTION:
{question}

GENERATED ANSWER:
{answer}

RETRIEVED EVIDENCE:
{evidence}

ACTUAL ROUTE:
{route_text}

EXPECTED ROUTE:
{expected_route_text}

Return ONLY one JSON object with these numeric fields, each from 0 to 100:

accuracy:
    Overall correctness of the generated answer. If expected route/ground truth
    is not supplied, judge correctness against the retrieved evidence and the
    question, and treat this as a model-based correctness estimate.

faithfulness:
    How completely the answer is supported by the retrieved evidence.

answer_relevance:
    How directly and usefully the answer addresses the user's question.

context_precision:
    How much of the retrieved evidence is relevant to the question.

context_recall:
    How completely the retrieved evidence covers the information needed to
    answer the question.

route_accuracy:
    Whether the selected route is appropriate for the question. If an expected
    route is supplied, compare actual route against it. If no expected route is
    supplied, judge routing appropriateness from the question.

Also return:

reason:
    A short explanation for the scores.

JSON schema:
{{
  "accuracy": 0,
  "faithfulness": 0,
  "answer_relevance": 0,
  "context_precision": 0,
  "context_recall": 0,
  "route_accuracy": 0,
  "reason": "..."
}}
"""

        try:
            response = await self.llm.acomplete(prompt)
            evaluator_cost_usd = self._usage_cost_from_raw(
                getattr(response, "raw", None)
            )
            parsed = self._extract_json(response.text)

            result = {
                "accuracy": self._score(parsed.get("accuracy")),
                "faithfulness": self._score(parsed.get("faithfulness")),
                "answer_relevance": self._score(parsed.get("answer_relevance")),
                "context_precision": self._score(parsed.get("context_precision")),
                "context_recall": self._score(parsed.get("context_recall")),
                "route_accuracy": self._score(parsed.get("route_accuracy")),
                "guardrail_effectiveness": (
                    100.0
                    if guardrail_allowed is True
                    else 0.0
                    if guardrail_allowed is False
                    else None
                ),
                "evaluator_cost_usd": evaluator_cost_usd,
                "quality_evaluation_available": True,
                "quality_evaluation_error": None,
                "quality_evaluation_reason": str(parsed.get("reason") or ""),
            }

            logger.info(
                "Production quality evaluation completed "
                "accuracy=%s faithfulness=%s relevance=%s "
                "context_precision=%s context_recall=%s route_accuracy=%s",
                result["accuracy"],
                result["faithfulness"],
                result["answer_relevance"],
                result["context_precision"],
                result["context_recall"],
                result["route_accuracy"],
            )

            return result

        except Exception as exc:  # noqa: BLE001
            logger.exception(
                "Production quality evaluation failed: %s",
                str(exc),
            )

            return {
                "accuracy": None,
                "faithfulness": None,
                "answer_relevance": None,
                "context_precision": None,
                "context_recall": None,
                "route_accuracy": None,
                "guardrail_effectiveness": (
                    100.0
                    if guardrail_allowed is True
                    else 0.0
                    if guardrail_allowed is False
                    else None
                ),
                "quality_evaluation_available": False,
                "quality_evaluation_error": str(exc),
            }
