from app.llm.complexity import assess_complexity


def test_complexity() -> None:
    test_cases = [
        (
            "How do I reset my password?",
            {},
            "simple",
        ),
        (
            "Why am I getting an API error?",
            {},
            "medium",
        ),
        (
            "Our production API is completely down.",
            {},
            "complex",
        ),
        (
            "We suspect a security breach and possible data exposure.",
            {},
            "complex",
        ),
        (
            "Compare these two API integration approaches.",
            {},
            "complex",
        ),
        (
            "The application is slow and users are experiencing latency.",
            {},
            "medium",
        ),
        (
            "Our billing subscription is showing the wrong amount.",
            {},
            "medium",
        ),
        (
            "The service is unavailable.",
            {
                "route": "incident",
            },
            "complex",
        ),
        (
            "How do I configure the API?",
            {
                "route": "rag",
            },
            "medium",
        ),
        (
            "Is my account active and why am I getting a 404 API error?",
            {
                "route": "hybrid",
            },
            "medium",
        ),
        (
            "The issue is affecting production users.",
            {
                "severity": "critical",
            },
            "complex",
        ),
    ]

    print("\n========================================")
    print("COMPLEXITY EVALUATOR TEST")
    print("========================================")

    for query, kwargs, expected in test_cases:
        actual = assess_complexity(
            query,
            **kwargs,
        )

        print(
            f"Expected: {expected:<8} "
            f"Actual: {actual:<8} "
            f"Query: {query}"
        )

        assert actual == expected

    print("\nALL COMPLEXITY TESTS PASSED")


if __name__ == "__main__":
    test_complexity()