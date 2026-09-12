from types import SimpleNamespace

import pytest
from sqlalchemy.exc import SQLAlchemyError

from app.agents.retrieval import retrieval_agent as ra_mod


@pytest.mark.asyncio
async def test_constructor_validates_args():
    with pytest.raises(ValueError):
        ra_mod.RetrievalAgent(similarity_top_k=0)

    with pytest.raises(ValueError):
        ra_mod.RetrievalAgent(minimum_similarity=-0.1)

    with pytest.raises(ValueError):
        ra_mod.RetrievalAgent(minimum_similarity=1.1)


@pytest.mark.asyncio
async def test_run_empty_query_returns_failure():
    svc = ra_mod.RetrievalAgent()
    out = await svc.run("")
    assert out["success"] is False
    assert out["confidence"] == 0.0


@pytest.mark.asyncio
async def test_run_with_session_uses_service(monkeypatch):
    # fake evidence below threshold
    class FakeRetrievalService:
        def __init__(self, session, similarity_top_k, minimum_similarity):
            pass

        async def retrieve_evidence(self, query):
            return [
                {"document_name": "d1", "vector_score": 0.3},
                {"document_name": "d2", "vector_score": 0.4},
            ]

    monkeypatch.setattr(ra_mod, "FusionRetrievalService", FakeRetrievalService)

    svc = ra_mod.RetrievalAgent(similarity_top_k=3, minimum_similarity=0.0)

    out = await svc.run("find docs", session=SimpleNamespace())

    assert out["success"] is True
    assert out["confidence"] == 0.4
    assert out["sufficient_evidence"] is False


@pytest.mark.asyncio
async def test_run_sufficient_evidence_true(monkeypatch):
    class FakeRetrievalService:
        def __init__(self, session, similarity_top_k, minimum_similarity):
            pass

        async def retrieve_evidence(self, query):
            return [
                {"document_name": "d1", "vector_score": 0.6},
                {"document_name": "d2", "vector_score": 0.55},
            ]

    monkeypatch.setattr(ra_mod, "FusionRetrievalService", FakeRetrievalService)

    svc = ra_mod.RetrievalAgent(similarity_top_k=3, minimum_similarity=0.0)

    out = await svc.run("find docs", session=SimpleNamespace())

    assert out["success"] is True
    assert out["confidence"] == 0.6
    assert out["sufficient_evidence"] is True


@pytest.mark.asyncio
async def test_run_handles_retrieval_errors(monkeypatch):
    class BadRetrievalService:
        def __init__(self, session, similarity_top_k, minimum_similarity):
            pass

        async def retrieve_evidence(self, query):
            raise SQLAlchemyError("boom")

    monkeypatch.setattr(ra_mod, "FusionRetrievalService", BadRetrievalService)

    svc = ra_mod.RetrievalAgent()

    out = await svc.run("q", session=SimpleNamespace())

    assert out["success"] is False
    assert "Documentation retrieval failed" in out["reason"]


@pytest.mark.asyncio
async def test_run_no_evidence_returns_ok(monkeypatch):
    class EmptyRetrievalService:
        def __init__(self, session, similarity_top_k, minimum_similarity):
            pass

        async def retrieve_evidence(self, query):
            return []

    monkeypatch.setattr(ra_mod, "FusionRetrievalService", EmptyRetrievalService)

    svc = ra_mod.RetrievalAgent()

    out = await svc.run("q", session=SimpleNamespace())

    assert out["success"] is True
    assert out["results"] == []
    assert out["confidence"] == 0.0
