from app.llm.gateway import LLMGateway, get_llm


def test_route_valid_and_invalid(monkeypatch):
    gw = LLMGateway()

    r = gw.route(complexity="simple")
    assert r.complexity == "simple"

    r2 = gw.route(complexity="complex")
    assert r2.complexity == "complex"

    # high_risk forces complex
    r3 = gw.route(complexity="simple", high_risk=True)
    assert r3.complexity == "complex"

    try:
        gw.route(complexity="unknown")
        assert False, "should have raised"
    except ValueError:
        pass


def test_get_llm_uses_provider(monkeypatch):
    class FakeLLM:
        pass

    # gateway imported create_groq_llm at module import time, patch there
    import app.llm.gateway as gateway_mod

    monkeypatch.setattr(gateway_mod, "create_groq_llm", lambda complexity: FakeLLM())

    llm = get_llm(complexity="simple")
    assert isinstance(llm, FakeLLM)
