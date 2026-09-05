from app.llm.gateway import LLMGateway


def main() -> None:

    gateway = LLMGateway()

    print("\n=== SIMPLE ===")

    route = gateway.route(
        complexity="simple"
    )

    print(route)

    assert route.provider == "groq"
    assert route.model == (
        "openai/gpt-oss-20b"
    )

    print("\n=== MEDIUM ===")

    route = gateway.route(
        complexity="medium"
    )

    print(route)

    assert route.provider == "groq"
    assert route.model == (
        "openai/gpt-oss-20b"
    )

    print("\n=== COMPLEX ===")

    route = gateway.route(
        complexity="complex"
    )

    print(route)

    assert route.provider == "groq"
    assert route.model == (
        "openai/gpt-oss-120b"
    )

    print("\n=== HIGH RISK OVERRIDE ===")

    route = gateway.route(
        complexity="simple",
        high_risk=True,
    )

    print(route)

    assert route.provider == "groq"
    assert route.model == (
        "openai/gpt-oss-120b"
    )

    print("\nALL LLM GATEWAY TESTS PASSED")


if __name__ == "__main__":
    main()