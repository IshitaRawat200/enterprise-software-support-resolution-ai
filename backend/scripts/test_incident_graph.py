from __future__ import annotations

import asyncio
import json

from app.orchestrator.graph import build_uncheckpointed_graph


async def main() -> None:
    state = {
        "message": (
            "Our enterprise API is currently unavailable "
            "in production and customers cannot make API requests."
        ),
        "conversation_id": None,
        "customer_id": "68c5f980-6de5-4303-bedc-8c8ec65532c2",
        "iteration": 0,
        "max_iterations": 2,
    }

    print("=" * 70)
    print("INCIDENT GRAPH TEST")
    print("=" * 70)
    
    support_graph = build_uncheckpointed_graph()

    result = await support_graph.ainvoke(state)

    print("\n--- WORKFLOW RESULT ---")
    print(
        json.dumps(
            result,
            indent=2,
            default=str,
        )
    )

    print("\n--- KEY RESULTS ---")

    print(
        "Intent:",
        result.get("intent"),
    )

    print(
        "Intent confidence:",
        result.get("intent_confidence"),
    )

    print(
        "Route:",
        result.get("route"),
    )

    print(
        "Selected action:",
        result.get("selected_action"),
    )

    print(
        "Incident active:",
        result.get("incident_active"),
    )

    print(
        "Incident status:",
        result.get("incident_status"),
    )

    print(
        "Incident code:",
        result.get("incident_code"),
    )

    print(
        "Incident severity:",
        result.get("incident_severity"),
    )

    print(
        "Incident affects production:",
        result.get("incident_affects_production"),
    )

    print(
        "MCP tool calls:",
        result.get("mcp_tool_calls"),
    )

    print(
        "Workflow severity:",
        result.get("severity"),
    )

    print(
        "Escalation required:",
        result.get("escalation_required"),
    )

    print(
        "Escalation reason:",
        result.get("escalation_reason"),
    )

    print(
        "Resolution:",
        result.get("resolution_reason"),
    )


if __name__ == "__main__":
    asyncio.run(main())