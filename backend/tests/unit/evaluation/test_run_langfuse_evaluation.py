from __future__ import annotations

import asyncio

from app.evaluation import run_langfuse_evaluation as rle


class _FakeSupportGraph:
    async def ainvoke(self, initial_state, config=None):
        return {
            "response": "Handle 500 with retry and escalation if persistent.",
            "intent": "api_errors",
            "route": "rag",
            "severity": "high",
            "escalation_required": True,
            "guardrail_action": "ALLOW",
            "retrieval_results": [{"content": "server-side errors troubleshooting"}],
            "errors": [],
        }


def test_resolve_expected_fields_normalizes_metadata_keys() -> None:
    item = {
        "input": "How should I handle HTTP 500, 502, 503, and 504 errors?",
        "metadata": {
            "Test ID": "Q015",
            "Category": "API Errors",
            "Expected Route": "RAG",
            "Expected Escalation": "Yes",
            "Expected Guardrail": "ALLOW",
            "Source PDF": "API Error Codes & Troubleshooting Handbook",
            "Source Section / Page": "Section 4",
            "SLOs to Evaluate": "Accuracy; Route Accuracy",
            "Expected SLO Targets": "Route Accuracy >=95%; Escalation Accuracy =100%",
        },
        "expected_output": {},
    }

    fields = rle._resolve_expected_fields(item)

    assert fields["category"] == "API Errors"
    assert fields["expected_route"] == "rag"
    assert fields["expected_escalation"] is True
    assert fields["expected_guardrail"] == "allow"
    assert fields["source_pdf"] == "API Error Codes & Troubleshooting Handbook"
    assert fields["source_section_page"] == "Section 4"
    assert fields["slos_to_evaluate"] == "Accuracy; Route Accuracy"
    assert "Route Accuracy" in fields["expected_slo_targets"]


def test_build_task_outputs_ground_truth_fields_without_csv() -> None:
    item = {
        "id": "langfuse-item-q015",
        "input": "How should I handle HTTP 500, 502, 503, and 504 errors?",
        "metadata": {
            "test_id": "Q015",
            "category": "API Errors",
            "expected_route": "RAG",
            "expected_escalation": "Yes",
            "expected_guardrail": "ALLOW",
            "source_pdf": "API Error Codes & Troubleshooting Handbook",
            "source_section_page": "Section 4",
            "slos_to_evaluate": "Accuracy; Route Accuracy",
            "expected_slo_targets": "Route Accuracy >=95%",
        },
        "expected_output": {},
    }

    task = asyncio.run(rle.build_task(_FakeSupportGraph()))
    output = asyncio.run(task(item=item))

    assert output["test_id"] == "Q015"
    assert output["ground_truth_available"] is True
    assert output["expected_route"] == "rag"
    assert output["expected_escalation"] is True
    assert output["expected_guardrail"] == "allow"
    assert output["category"] == "API Errors"
    assert output["source_pdf"] == "API Error Codes & Troubleshooting Handbook"
    assert output["source_section_page"] == "Section 4"
    assert output["slos_to_evaluate"] == "Accuracy; Route Accuracy"
