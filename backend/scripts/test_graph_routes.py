from __future__ import annotations

import asyncio
import json

from app.orchestrator.graph import build_uncheckpointed_graph


CUSTOMER_ID = "68c5f980-6de5-4303-bedc-8c8ec65532c2"


TEST_CASES = [
    {
        "name": "RAG",
        "message": (
            "What does a 404 Not Found response mean "
            "in the Enterprise API documentation?"
        ),
    },
    {
        "name": "SQL",
        "message": (
            "Is my account currently active?"
        ),
    },
    {
        "name": "HYBRID",
        "message": (
            "How do I troubleshoot a 404 API error, "
            "and is my account currently active?"
        ),
    },
]

async def run_test(
    name: str,
    message: str,
) -> dict:
    print("\n")
    print("=" * 80)
    print(f"{name} ROUTE TEST")
    print("=" * 80)

    state = {
        "message": message,
        "conversation_id": None,
        "customer_id": CUSTOMER_ID,
        "iteration": 0,
        "max_iterations": 2,
    }

    print("\nINPUT")
    print("-" * 80)
    print(message)
    support_graph = build_uncheckpointed_graph()
    result = await support_graph.ainvoke(state)

    print("\nKEY RESULTS")
    print("-" * 80)

    print(
        f"Intent:                 "
        f"{result.get('intent')}"
    )

    print(
        f"Intent confidence:      "
        f"{result.get('intent_confidence')}"
    )

    print(
        f"Suggested route:        "
        f"{result.get('suggested_route')}"
    )

    print(
        f"Actual route:           "
        f"{result.get('route')}"
    )

    print(
        f"Selected action:        "
        f"{result.get('selected_action')}"
    )

    print(
        f"RAG confidence:        "
        f"{result.get('retrieval_confidence')}"
    )

    print(
        f"SQL success:             "
        f"{result.get('sql_success')}"
    )

    print(
        f"SQL confidence:          "
        f"{result.get('sql_confidence')}"
    )

    print(
        f"Hybrid success:          "
        f"{result.get('hybrid_success')}"
    )

    print(
        f"Hybrid confidence:       "
        f"{result.get('hybrid_confidence')}"
    )

    print(
        f"Check passed:            "
        f"{result.get('check_passed')}"
    )

    print(
        f"Reflection decision:     "
        f"{result.get('reflection_decision')}"
    )

    print(
        f"Severity:                "
        f"{result.get('severity')}"
    )

    print(
        f"Escalation required:     "
        f"{result.get('escalation_required')}"
    )

    print(
        f"Errors:                  "
        f"{result.get('errors')}"
    )

    print("\nROUTE-SPECIFIC EVIDENCE")
    print("-" * 80)

    route = result.get("route")

    if route == "rag":
        print(
            json.dumps(
                result.get("retrieval_results", []),
                indent=2,
                default=str,
            )
        )

    elif route == "sql":
        print(
            "SQL query:"
        )
        print(
            result.get("sql_query")
        )

        print("\nSQL rows:")
        print(
            json.dumps(
                result.get("sql_rows", []),
                indent=2,
                default=str,
            )
        )

    elif route == "hybrid":
        print(
            json.dumps(
                result.get("hybrid_results", []),
                indent=2,
                default=str,
            )
        )

    else:
        print(
            f"No RAG/SQL/Hybrid evidence "
            f"because route was '{route}'."
        )

    return result


def validate_result(
    name: str,
    result: dict,
) -> bool:
    route = result.get("route")
    errors = result.get("errors") or []

    expected_route = {
        "RAG": "rag",
        "SQL": "sql",
        "HYBRID": "hybrid",
    }.get(name)

    passed = True

    if route != expected_route:
        print(
            f"\n❌ {name}: expected route "
            f"'{expected_route}', got '{route}'"
        )
        passed = False

    if errors:
        print(
            f"\n❌ {name}: workflow returned errors:"
        )

        for error in errors:
            print(f"   - {error}")

        passed = False

    if not result.get("check_passed", False):
        print(
            f"\n❌ {name}: CHECK did not pass."
        )
        passed = False

    if passed:
        print(
            f"\n✅ {name} ROUTE TEST PASSED"
        )

    return passed


async def main() -> None:
    print("=" * 80)
    print("LANGGRAPH ROUTE INTEGRATION TEST")
    print("=" * 80)

    results: dict[str, dict] = {}

    for test_case in TEST_CASES:
        name = test_case["name"]
        message = test_case["message"]

        try:
            result = await run_test(
                name=name,
                message=message,
            )

            results[name] = result

        except Exception as exc:
            print("\n")
            print("=" * 80)
            print(f"❌ {name} ROUTE TEST FAILED")
            print("=" * 80)
            print(
                f"{type(exc).__name__}: {exc}"
            )

            results[name] = {
                "route": None,
                "errors": [
                    f"{type(exc).__name__}: {exc}"
                ],
                "check_passed": False,
            }

    print("\n")
    print("=" * 80)
    print("VALIDATION SUMMARY")
    print("=" * 80)

    all_passed = True

    for name, result in results.items():
        passed = validate_result(
            name=name,
            result=result,
        )

        if not passed:
            all_passed = False

    print("\n")
    print("=" * 80)

    if all_passed:
        print("✅ ALL RAG / SQL / HYBRID ROUTE TESTS PASSED")
    else:
        print("❌ ONE OR MORE ROUTE TESTS FAILED")

    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())