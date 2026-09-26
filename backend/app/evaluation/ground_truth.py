from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class EvaluationCase:
    """
    Curated ground-truth case used for production evaluation.

    reference_answer:
        Trusted answer used by Context Precision and Context Recall.

    expected_route:
        Trusted expected route used by Route Accuracy.
    """

    question: str
    reference_answer: str
    expected_route: str


# ============================================================
# CURATED PRODUCTION EVALUATION CASES
# ============================================================
#
# IMPORTANT:
# Only put reviewed/trusted answers here.
#
# Never automatically use the AI-generated answer as the
# reference answer.
#
# Add more cases as your evaluation dataset grows.
# ============================================================

EVALUATION_CASES: tuple[EvaluationCase, ...] = (
    EvaluationCase(
        question=(
            "What should I do if the ERIS database connection "
            "is refused during setup?"
        ),
        expected_route="rag",
        reference_answer=(
            "If the ERIS database connection is refused during setup, "
            "verify that PostgreSQL is running and reachable, check that "
            "DB_HOST, DB_PORT, DB_NAME, DB_USER, and DB_PASSWORD are correct, "
            "ensure port 5432 is allowed through the firewall or security "
            "group, and restart ERIS after correcting the configuration."
        ),
    ),

    EvaluationCase(
        question="Which ports must be open for an ERIS deployment?",
        expected_route="rag",
        reference_answer=(
            "The required ERIS deployment ports are "
            "80, 443, 5432, 6379, and 8080."
        ),
    ),

    EvaluationCase(
        question=(
            "How often should production API keys be rotated "
            "and where should they be stored?"
        ),
        expected_route="rag",
        reference_answer=(
            "Production API keys should be rotated every 90 days "
            "or immediately if compromised. They should be stored "
            "in environment variables or a secrets manager."
        ),
    ),
)


# ============================================================
# NORMALIZATION
# ============================================================


def _normalize_question(question: str) -> str:
    return " ".join(
        str(question).strip().lower().split()
    )


# Exact-match lookup.

_CASES_BY_QUESTION: dict[str, EvaluationCase] = {
    _normalize_question(case.question): case
    for case in EVALUATION_CASES
}


# ============================================================
# PUBLIC API
# ============================================================


def get_evaluation_case(
    question: str,
) -> EvaluationCase | None:
    """
    Return a trusted evaluation case.

    Unknown production questions return None.

    This is intentional: we must not invent ground truth.
    """

    if not question:
        return None

    return _CASES_BY_QUESTION.get(
        _normalize_question(question)
    )


def get_reference_answer(
    question: str,
) -> str | None:
    case = get_evaluation_case(question)

    if case is None:
        return None

    return case.reference_answer


def get_expected_route(
    question: str,
) -> str | None:
    case = get_evaluation_case(question)

    if case is None:
        return None

    return case.expected_route