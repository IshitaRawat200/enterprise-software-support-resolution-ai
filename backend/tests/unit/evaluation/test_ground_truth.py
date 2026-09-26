from __future__ import annotations

from pathlib import Path

from app.evaluation import ground_truth as gt


def _clear_ground_truth_caches() -> None:
    gt._load_evaluation_cases.cache_clear()
    gt._cases_by_question.cache_clear()
    gt._cases_by_test_id.cache_clear()


def test_ground_truth_falls_back_to_local_csv_when_langfuse_missing(
    monkeypatch,
    tmp_path: Path,
) -> None:
    csv_path = tmp_path / "golden.csv"
    csv_path.write_text(
        "Test ID,Category,Input / Query,Expected Route,Expected Escalation,Expected Guardrail,Expected Output\n"
        'Q035,Hybrid API Error,"My current ticket reports repeated HTTP 429 responses. What does the policy say I should do, and what ticket information should I review?",HYBRID,No,ALLOW,"Use ticket details plus the API handbook: inspect Retry-After/rate-limit headers, wait as documented, implement exponential backoff, reduce concurrent requests, and check quota information."\n',
        encoding="utf-8",
    )

    monkeypatch.setattr(gt, "LOCAL_GOLDEN_SET_PATH", csv_path)
    monkeypatch.setattr(
        gt, "_load_dataset_items", lambda dataset_name=gt.DATASET_NAME: []
    )

    _clear_ground_truth_caches()

    case = gt.get_evaluation_case(
        "My current ticket reports repeated HTTP 429 responses. What does the policy say I should do, and what ticket information should I review?"
    )

    assert case is not None
    assert case.test_id == "Q035"
    assert case.expected_route == "hybrid"
    assert "retry-after" in case.reference_answer.lower()


def test_ground_truth_case_lookup_by_test_id_uses_local_csv(
    monkeypatch,
    tmp_path: Path,
) -> None:
    csv_path = tmp_path / "golden.csv"
    csv_path.write_text(
        "Test ID,Category,Input / Query,Expected Route,Expected Escalation,Expected Guardrail,Expected Output\n"
        "Q036,Hybrid Performance,My ticket says GET /tickets is slow. What P95 target should I compare against and what operational data should I inspect?,HYBRID,No,ALLOW,Compare against the 150 ms P95 target and inspect ticket/request performance data plus caching and pagination.\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(gt, "LOCAL_GOLDEN_SET_PATH", csv_path)
    monkeypatch.setattr(
        gt, "_load_dataset_items", lambda dataset_name=gt.DATASET_NAME: []
    )

    _clear_ground_truth_caches()

    case = gt.get_evaluation_case_by_test_id("Q036")

    assert case is not None
    assert case.expected_route == "hybrid"
    assert case.question.startswith("My ticket says GET /tickets is slow")
