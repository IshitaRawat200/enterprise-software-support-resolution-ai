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
        def with_fallbacks(self, fallbacks):
            self.fallbacks = fallbacks
            return self

    # gateway imported create_groq_llm at module import time, patch there
    import app.llm.gateway as gateway_mod

    monkeypatch.setattr(gateway_mod, "create_groq_llm", lambda complexity: FakeLLM())
    monkeypatch.setattr(gateway_mod, "create_openrouter_llm", lambda: FakeLLM())

    llm = get_llm(complexity="simple")
    assert isinstance(llm, FakeLLM)


def test_get_llm_uses_openrouter_fallback_when_groq_is_exhausted(monkeypatch):
    import app.llm.gateway as gateway_mod

    class FakeGroq:
        def __init__(self):
            self.fallbacks = []

        def with_fallbacks(self, fallbacks):
            self.fallbacks = fallbacks
            return self

    class FakeOpenRouter:
        pass

    monkeypatch.setattr(gateway_mod, "create_groq_llm", lambda complexity: FakeGroq())
    monkeypatch.setattr(gateway_mod, "create_openrouter_llm", lambda: FakeOpenRouter())

    llm = gateway_mod.LLMGateway().get_llm(complexity="simple")

    assert isinstance(llm, FakeGroq)
    assert any(isinstance(item, FakeOpenRouter) for item in llm.fallbacks)


def test_get_llm_adds_openrouter_fallback_for_complex_workload(monkeypatch):
    import app.llm.gateway as gateway_mod

    class FakeGroq:
        def __init__(self):
            self.fallbacks = []

        def with_fallbacks(self, fallbacks):
            self.fallbacks = fallbacks
            return self

    class FakeOpenRouter:
        pass

    monkeypatch.setattr(gateway_mod, "create_groq_llm", lambda complexity: FakeGroq())
    monkeypatch.setattr(gateway_mod, "create_openrouter_llm", lambda: FakeOpenRouter())

    llm = gateway_mod.LLMGateway().get_llm(complexity="complex")

    assert isinstance(llm, FakeGroq)
    assert any(isinstance(item, FakeOpenRouter) for item in llm.fallbacks)
