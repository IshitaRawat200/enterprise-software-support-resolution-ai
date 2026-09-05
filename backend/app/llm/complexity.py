from __future__ import annotations

from typing import Literal


Complexity = Literal["simple", "medium", "complex"]


COMPLEX_KEYWORDS = [
    "analyze",
    "analyse",
    "analysis",
    "evaluate",
    "evaluation",
    "compare",
    "comparison",
    "recommend",
    "recommendation",
    "strategy",
    "strategic",
    "optimize",
    "optimization",
    "risk analysis",
    "market analysis",
    "competitor analysis",
    "business model",
    "roadmap",
]


MEDIUM_KEYWORDS = [
    "performance",
    "latency",
    "slow",
    "timeout",
    "integration",
    "api",
    "multiple",
    "investigate",
    "investigation",
    "billing",
    "subscription",
    "configuration",
    "error",
    "failure",
]


HIGH_RISK_KEYWORDS = [
    "production outage",
    "production down",
    "production is down",
    "production completely down",
    "service outage",
    "system outage",
    "all customers",
    "everyone is affected",
    "security breach",
    "data breach",
    "data exposure",
    "data leak",
    "credential compromised",
    "api key compromised",
    "api key leaked",
    "security vulnerability",
]


def assess_complexity(
    query: str,
    *,
    route: str | None = None,
    severity: str | None = None,
) -> Complexity:
    """
    Determine the reasoning complexity of a support request.

    This function only determines complexity.

    It does NOT select the LLM model.
    Model selection is handled by the LLM Gateway.
    """

    query_lower = query.lower().strip()
    word_count = len(query.split())

    # ---------------------------------------------------------
    # 1. High-risk keywords
    # ---------------------------------------------------------

    if any(
        keyword in query_lower
        for keyword in HIGH_RISK_KEYWORDS
    ):
        complexity: Complexity = "complex"

        print("\n===== COMPLEXITY EVALUATOR =====")
        print(f"Question: {query}")
        print("Reason: high-risk keyword detected")
        print(f"Complexity: {complexity}")
        print("================================\n")

        return complexity

    # ---------------------------------------------------------
    # 2. Production outage patterns
    # ---------------------------------------------------------

    production_words = [
        "production",
        "prod",
    ]

    outage_words = [
        "down",
        "outage",
        "unavailable",
        "offline",
        "not working",
        "completely unavailable",
    ]

    has_production = any(
        word in query_lower
        for word in production_words
    )

    has_outage = any(
        word in query_lower
        for word in outage_words
    )

    if has_production and has_outage:
        complexity = "complex"

        print("\n===== COMPLEXITY EVALUATOR =====")
        print(f"Question: {query}")
        print("Reason: production outage pattern detected")
        print(f"Complexity: {complexity}")
        print("================================\n")

        return complexity

    # ---------------------------------------------------------
    # 3. Critical severity
    # ---------------------------------------------------------

    if severity == "critical":
        complexity = "complex"

        print("\n===== COMPLEXITY EVALUATOR =====")
        print(f"Question: {query}")
        print("Reason: critical severity")
        print(f"Complexity: {complexity}")
        print("================================\n")

        return complexity

    # ---------------------------------------------------------
    # 4. Incident route
    # ---------------------------------------------------------

    if route == "incident":
        complexity = "complex"

        print("\n===== COMPLEXITY EVALUATOR =====")
        print(f"Question: {query}")
        print("Reason: incident route")
        print(f"Complexity: {complexity}")
        print("================================\n")

        return complexity

    # ---------------------------------------------------------
    # 5. Explicit complex reasoning keywords
    # ---------------------------------------------------------

    if any(
        keyword in query_lower
        for keyword in COMPLEX_KEYWORDS
    ):
        complexity = "complex"

        print("\n===== COMPLEXITY EVALUATOR =====")
        print(f"Question: {query}")
        print("Reason: complex reasoning keyword detected")
        print(f"Complexity: {complexity}")
        print("================================\n")

        return complexity

    # ---------------------------------------------------------
    # 6. Medium-complexity support keywords
    # ---------------------------------------------------------

    if any(
        keyword in query_lower
        for keyword in MEDIUM_KEYWORDS
    ):
        complexity = "medium"

        print("\n===== COMPLEXITY EVALUATOR =====")
        print(f"Question: {query}")
        print("Reason: medium-complexity support keyword detected")
        print(f"Complexity: {complexity}")
        print("================================\n")

        return complexity

    # ---------------------------------------------------------
    # 7. Hybrid route
    # ---------------------------------------------------------

    if route == "hybrid":
        complexity = "medium"

        print("\n===== COMPLEXITY EVALUATOR =====")
        print(f"Question: {query}")
        print("Reason: hybrid route")
        print(f"Complexity: {complexity}")
        print("================================\n")

        return complexity

    # ---------------------------------------------------------
    # 8. Long request
    # ---------------------------------------------------------

    if word_count > 40:
        complexity = "medium"

        print("\n===== COMPLEXITY EVALUATOR =====")
        print(f"Question: {query}")
        print(f"Word count: {word_count}")
        print("Reason: long request")
        print(f"Complexity: {complexity}")
        print("================================\n")

        return complexity

    # ---------------------------------------------------------
    # 9. Default
    # ---------------------------------------------------------

    complexity = "simple"

    print("\n===== COMPLEXITY EVALUATOR =====")
    print(f"Question: {query}")
    print("Reason: no complexity triggers detected")
    print(f"Complexity: {complexity}")
    print("================================\n")

    return complexity