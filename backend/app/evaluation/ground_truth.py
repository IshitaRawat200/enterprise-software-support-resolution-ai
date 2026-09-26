from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

from langfuse import get_client


DATASET_NAME = "ERIS-Golden-50"


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
    test_id: str | None = None
    expected_escalation: bool | None = None
    expected_guardrail: str | None = None


def _normalize_key(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "_", value.strip().lower())
    return normalized.strip("_")


def _row_get(row: dict[str, Any], *keys: str) -> Any:
    normalized_row = {
        _normalize_key(str(key)): value for key, value in row.items() if key is not None
    }

    for key in keys:
        value = normalized_row.get(_normalize_key(key))
        if value not in (None, ""):
            return value

    return None


def _parse_bool(value: Any) -> bool | None:
    if value is None:
        return None

    text = str(value).strip().lower()

    if text in {"yes", "true", "1", "y"}:
        return True

    if text in {"no", "false", "0", "n"}:
        return False

    return None


def _item_as_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value

    return {}


def _item_input(item: Any) -> str:
    if isinstance(item, dict):
        return str(item.get("input") or "")

    return str(getattr(item, "input", "") or "")


def _item_metadata(item: Any) -> dict[str, Any]:
    if isinstance(item, dict):
        return _item_as_dict(item.get("metadata"))

    return _item_as_dict(getattr(item, "metadata", None))


def _item_expected_output(item: Any) -> dict[str, Any]:
    if isinstance(item, dict):
        return _item_as_dict(item.get("expected_output"))

    return _item_as_dict(getattr(item, "expected_output", None))


def _load_dataset_items(dataset_name: str = DATASET_NAME) -> list[Any]:
    langfuse = get_client()
    dataset = langfuse.get_dataset(dataset_name)
    return list(dataset.items)


@lru_cache(maxsize=1)
def _load_evaluation_cases() -> tuple[EvaluationCase, ...]:
    try:
        items = _load_dataset_items()
    except Exception:
        return tuple()

    cases: list[EvaluationCase] = []

    for item in items:
        metadata = _item_metadata(item)
        expected_output = _item_expected_output(item)

        question = _item_input(item)
        reference_answer = _row_get(expected_output, "expected output", "reference answer", "answer")

        if reference_answer in (None, ""):
            reference_answer = _row_get(metadata, "expected output", "reference answer")

        expected_route = _row_get(expected_output, "expected route", "expected_route", "route")
        if expected_route in (None, ""):
            expected_route = _row_get(metadata, "expected route", "expected_route")

        if not question or not reference_answer or not expected_route:
            continue

        test_id = _row_get(metadata, "test id", "test_id", "id", "case_id", "case id")
        expected_escalation = _parse_bool(
            _row_get(
                expected_output,
                "expected escalation",
                "expected_escalation",
                "escalation",
            )
        )
        if expected_escalation is None:
            expected_escalation = _parse_bool(
                _row_get(
                    metadata,
                    "expected escalation",
                    "expected_escalation",
                )
            )

        expected_guardrail = _row_get(
            expected_output,
            "expected guardrail",
            "expected_guardrail",
            "expected guardrail action",
            "expected_guardrail_action",
        )
        if expected_guardrail in (None, ""):
            expected_guardrail = _row_get(
                metadata,
                "expected guardrail",
                "expected_guardrail",
                "expected guardrail action",
                "expected_guardrail_action",
            )

        cases.append(
            EvaluationCase(
                question=str(question).strip(),
                reference_answer=str(reference_answer).strip(),
                expected_route=str(expected_route).strip().lower(),
                test_id=(
                    str(test_id).strip()
                    if test_id not in (None, "") and str(test_id).strip().lower() not in {"none", "null"}
                    else None
                ),
                expected_escalation=expected_escalation,
                expected_guardrail=(str(expected_guardrail).strip().lower() if expected_guardrail else None),
            )
        )

    return tuple(cases)


# ============================================================
# NORMALIZATION
# ============================================================


def _normalize_question(question: str) -> str:
    return " ".join(
        str(question).strip().lower().split()
    )


# Exact-match lookup.

_CASES_BY_QUESTION: dict[str, EvaluationCase] = {
    _normalize_question(case.question): case for case in _load_evaluation_cases()
}

_CASES_BY_TEST_ID: dict[str, EvaluationCase] = {
    str(case.test_id).strip().lower(): case
    for case in _load_evaluation_cases()
    if case.test_id
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


def get_evaluation_case_by_test_id(test_id: str) -> EvaluationCase | None:
    if not test_id:
        return None

    return _CASES_BY_TEST_ID.get(str(test_id).strip().lower())