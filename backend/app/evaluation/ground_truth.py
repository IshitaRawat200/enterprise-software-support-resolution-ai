from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from langfuse import get_client

DATASET_NAME = "ERIS-Golden-50"
LOCAL_GOLDEN_SET_PATH = (
    Path(__file__).resolve().parents[3]
    / "ERIS-Golden-50-with-SLO-Targets (1).csv"
)


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


def _build_case(
    *,
    question: Any,
    reference_answer: Any,
    expected_route: Any,
    test_id: Any = None,
    expected_escalation: Any = None,
    expected_guardrail: Any = None,
) -> EvaluationCase | None:
    if not question or not reference_answer or not expected_route:
        return None

    normalized_test_id: str | None = None
    if test_id not in (None, ""):
        candidate = str(test_id).strip()
        if candidate and candidate.lower() not in {"none", "null"}:
            normalized_test_id = candidate

    return EvaluationCase(
        question=str(question).strip(),
        reference_answer=str(reference_answer).strip(),
        expected_route=str(expected_route).strip().lower(),
        test_id=normalized_test_id,
        expected_escalation=_parse_bool(expected_escalation),
        expected_guardrail=(
            str(expected_guardrail).strip().lower()
            if expected_guardrail not in (None, "")
            else None
        ),
    )


def _load_csv_evaluation_cases() -> tuple[EvaluationCase, ...]:
    if not LOCAL_GOLDEN_SET_PATH.exists():
        return tuple()

    cases: list[EvaluationCase] = []

    with LOCAL_GOLDEN_SET_PATH.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)

        for row in reader:
            case = _build_case(
                question=_row_get(row, "Input / Query", "Input", "Query"),
                reference_answer=_row_get(row, "Expected Output", "Reference Answer", "Answer"),
                expected_route=_row_get(row, "Expected Route", "Route"),
                test_id=_row_get(row, "Test ID", "Case ID", "ID"),
                expected_escalation=_row_get(
                    row,
                    "Expected Escalation",
                    "Escalation",
                ),
                expected_guardrail=_row_get(
                    row,
                    "Expected Guardrail",
                    "Expected Guardrail Action",
                ),
            )

            if case is not None:
                cases.append(case)

    return tuple(cases)


@lru_cache(maxsize=1)
def _load_evaluation_cases() -> tuple[EvaluationCase, ...]:
    cases_by_question: dict[str, EvaluationCase] = {}
    cases_by_test_id: dict[str, EvaluationCase] = {}

    try:
        items = _load_dataset_items()
    except Exception:
        items = []

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

        case = _build_case(
            question=question,
            reference_answer=reference_answer,
            expected_route=expected_route,
            test_id=test_id,
            expected_escalation=expected_escalation,
            expected_guardrail=expected_guardrail,
        )

        if case is None:
            continue

        cases_by_question[_normalize_question(case.question)] = case
        if case.test_id:
            cases_by_test_id[str(case.test_id).strip().lower()] = case

    for case in _load_csv_evaluation_cases():
        normalized_question = _normalize_question(case.question)
        cases_by_question.setdefault(normalized_question, case)

        if case.test_id:
            cases_by_test_id.setdefault(str(case.test_id).strip().lower(), case)

    ordered_cases = list(cases_by_question.values())

    for case in cases_by_test_id.values():
        if case not in ordered_cases:
            ordered_cases.append(case)

    return tuple(ordered_cases)


# ============================================================
# NORMALIZATION
# ============================================================


def _normalize_question(question: str) -> str:
    return " ".join(
        str(question).strip().lower().split()
    )


@lru_cache(maxsize=1)
def _cases_by_question() -> dict[str, EvaluationCase]:
    return {
        _normalize_question(case.question): case
        for case in _load_evaluation_cases()
    }


@lru_cache(maxsize=1)
def _cases_by_test_id() -> dict[str, EvaluationCase]:
    return {
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

    return _cases_by_question().get(
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

    return _cases_by_test_id().get(str(test_id).strip().lower())