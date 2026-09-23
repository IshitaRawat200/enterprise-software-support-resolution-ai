from __future__ import annotations

import json
from typing import Any

from groq import AsyncGroq

from app.config import get_settings


class LLMJudge:
    """
    Independent LLM-based evaluator for ERIS responses.

    The judge evaluates:
        - Faithfulness
        - Answer relevance
        - Context precision
        - Context recall
        - Overall answer quality

    Scores are returned on a 0-100 scale.
    """

    def __init__(self) -> None:
        settings = get_settings()

        if not settings.groq_api_key:
            raise RuntimeError(
                "GROQ_API_KEY is not configured."
            )

        if not settings.groq_simple_model:
            raise RuntimeError(
                "GROQ_SIMPLE_MODEL is not configured."
            )

        self.client = AsyncGroq(
            api_key=settings.groq_api_key,
            base_url=settings.groq_base_url,
        )

        self.model = settings.groq_simple_model

    async def evaluate(
        self,
        *,
        question: str,
        response: str,
        retrieved_context: list[dict[str, Any]],
        expected_claims: list[str] | None = None,
    ) -> dict[str, Any]:
        """
        Evaluate one ERIS response.

        Returns scores from 0 to 100.
        """

        # ====================================================
        # RETRIEVED EVIDENCE
        # ====================================================

        context_parts: list[str] = []

        for index, item in enumerate(
            retrieved_context,
            start=1,
        ):
            if isinstance(item, dict):
                content = (
                    item.get("content")
                    or item.get("text")
                    or item.get("chunk")
                    or ""
                )

                if not content:
                    content = json.dumps(
                        item,
                        ensure_ascii=False,
                        default=str,
                    )
            else:
                content = str(item)

            context_parts.append(
                f"[Evidence {index}]\n{content}"
            )

        context = "\n\n".join(
            context_parts
        )

        # ====================================================
        # EXPECTED CLAIMS
        # ====================================================

        claims = expected_claims or []

        # ====================================================
        # JUDGE PROMPT
        # ====================================================

        prompt = f"""
You are the independent evaluation judge for ERIS
(Enterprise Software Support & Resolution Intelligence System).

Your job is to evaluate the answer produced by ERIS.

Do NOT judge whether you personally like the answer.
Judge it against the user's question, expected claims,
and supplied evidence.

USER QUESTION:
{question}

ERIS RESPONSE:
{response}

EXPECTED CLAIMS:
{json.dumps(claims, ensure_ascii=False)}

RETRIEVED EVIDENCE:
{context}

Evaluate the response using these criteria.

1. FAITHFULNESS
Does the ERIS response make claims that are supported by
the supplied retrieved evidence?

2. ANSWER RELEVANCE
Does the response directly and appropriately answer
the user's question?

3. CONTEXT PRECISION
How much of the supplied retrieved evidence is actually
relevant to answering the question?

4. CONTEXT RECALL
Does the supplied evidence contain the information needed
to answer the question and satisfy the expected claims?

5. OVERALL SCORE
Considering correctness, evidence support, relevance,
completeness, and usefulness, give an overall score.

Scoring:

0 = completely incorrect or unsupported
25 = mostly incorrect
50 = partially correct
75 = mostly correct
100 = fully correct and well supported

Return ONLY valid JSON.

Required format:

{{
    "faithfulness": 0,
    "answer_relevance": 0,
    "context_precision": 0,
    "context_recall": 0,
    "overall_score": 0,
    "reason": "short explanation"
}}
"""

        # ====================================================
        # CALL JUDGE MODEL
        # ====================================================

        completion = await self.client.chat.completions.create(
            model=self.model,
            temperature=0,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a strict and objective evaluation "
                        "judge. Return valid JSON only."
                    ),
                },
                {
                    "role": "user",
                    "content": prompt,
                },
            ],
        )

        content = (
            completion.choices[0]
            .message
            .content
            or "{}"
        )

        # ====================================================
        # PARSE RESULT
        # ====================================================

        try:
            result = json.loads(content)
        except json.JSONDecodeError as exc:
            raise ValueError(
                "LLM judge returned invalid JSON: "
                f"{content}"
            ) from exc

        # ====================================================
        # NORMALIZE SCORES
        # ====================================================

        return {
            "faithfulness": self._score(
                result.get("faithfulness")
            ),
            "answer_relevance": self._score(
                result.get("answer_relevance")
            ),
            "context_precision": self._score(
                result.get("context_precision")
            ),
            "context_recall": self._score(
                result.get("context_recall")
            ),
            "overall_score": self._score(
                result.get("overall_score")
            ),
            "reason": str(
                result.get("reason")
                or ""
            ),
        }

    @staticmethod
    def _score(
        value: Any,
    ) -> float:
        """
        Convert a judge value into a safe 0-100 score.
        """

        try:
            return max(
                0.0,
                min(
                    100.0,
                    float(value),
                ),
            )

        except (
            TypeError,
            ValueError,
        ):
            return 0.0