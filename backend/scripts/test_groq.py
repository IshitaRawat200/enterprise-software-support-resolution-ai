from __future__ import annotations

import asyncio

from app.llm.gateway import get_llm


async def main() -> None:
    print("\n========================================")
    print("GROQ LLM GATEWAY TEST")
    print("========================================")

    # ---------------------------------------------------------
    # SIMPLE
    # ---------------------------------------------------------

    print("\n--- SIMPLE ---")

    simple_llm = get_llm(
        complexity="simple"
    )

    simple_response = await simple_llm.ainvoke(
        "Say hello in one short sentence."
    )

    print("Model:", simple_llm.model_name)
    print("Response:", simple_response.content)

    # ---------------------------------------------------------
    # MEDIUM
    # ---------------------------------------------------------

    print("\n--- MEDIUM ---")

    medium_llm = get_llm(
        complexity="medium"
    )

    medium_response = await medium_llm.ainvoke(
        "Briefly explain why an API might experience latency."
    )

    print("Model:", medium_llm.model_name)
    print("Response:", medium_response.content)

    # ---------------------------------------------------------
    # COMPLEX
    # ---------------------------------------------------------

    print("\n--- COMPLEX ---")

    complex_llm = get_llm(
        complexity="complex"
    )

    complex_response = await complex_llm.ainvoke(
        "Compare two possible approaches for diagnosing "
        "a distributed production API outage."
    )

    print("Model:", complex_llm.model_name)
    print("Response:", complex_response.content)

    print("\n========================================")
    print("GROQ LLM GATEWAY TEST COMPLETED")
    print("========================================")


if __name__ == "__main__":
    asyncio.run(main())