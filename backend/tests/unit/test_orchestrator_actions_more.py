import asyncio
from types import SimpleNamespace

import pytest

from app.orchestrator.actions import hybrid_action, rag_action, sql_action


def _make_db_session_gen(session=None):
    async def gen():
        if session is not None:
            yield session

    return gen


def test_run_rag_success(monkeypatch):
    # Fake RetrievalAgent
    class FakeRA:
        def __init__(self, similarity_top_k=5):
            pass

        async def run(self, query, session):
            return {
                "results": [{"title": "T"}],
                "confidence": 0.8,
                "sufficient_evidence": True,
                "reason": "ok",
            }

    monkeypatch.setattr(rag_action, "RetrievalAgent", FakeRA)

    # fake db session generator
    monkeypatch.setattr(
        rag_action, "get_db_session", _make_db_session_gen(SimpleNamespace())
    )

    out = asyncio.run(rag_action.run_rag({"message": "hi"}))
    assert out["retrieval_confidence"] == pytest.approx(0.8)
    assert out["sufficient_evidence"] is True


def test_run_rag_no_db(monkeypatch):
    monkeypatch.setattr(rag_action, "get_db_session", _make_db_session_gen(None))

    out = asyncio.run(rag_action.run_rag({"message": "hi"}))
    assert "Unable to obtain a database session" in out["errors"][0]


def test_run_rag_agent_exception(monkeypatch):
    class BadRA:
        def __init__(self, similarity_top_k=5):
            pass

        async def run(self, query, session):
            raise RuntimeError("fail")

    monkeypatch.setattr(rag_action, "RetrievalAgent", BadRA)
    monkeypatch.setattr(
        rag_action, "get_db_session", _make_db_session_gen(SimpleNamespace())
    )

    out = asyncio.run(rag_action.run_rag({"message": "hi"}))
    assert "Documentation retrieval failed" in out["errors"][0]


def test_run_sql_success_and_failure(monkeypatch):
    # success path
    class FakeSQLService:
        def __init__(self, session):
            pass

        async def query(self, question, customer_id=None):
            return {
                "success": True,
                "sql": "SELECT 1",
                "rows": [{"a": 1}],
                "row_count": 1,
                "sql_confidence": 0.9,
                "explanation": "ok",
                "tables_used": ["t"],
            }

    monkeypatch.setattr(sql_action, "SQLService", FakeSQLService)
    monkeypatch.setattr(
        sql_action, "get_db_session", _make_db_session_gen(SimpleNamespace())
    )

    out = asyncio.run(sql_action.run_sql({"message": "q", "customer_id": "c"}))
    assert out["sql_success"] is True
    assert out["sql_row_count"] == 1

    # failure path
    class FakeSQLServiceFail:
        def __init__(self, session):
            pass

        async def query(self, question, customer_id=None):
            return {
                "success": False,
                "sql": "SELECT BAD",
                "error": "err",
                "confidence": 0.0,
            }

    monkeypatch.setattr(sql_action, "SQLService", FakeSQLServiceFail)
    out2 = asyncio.run(sql_action.run_sql({"message": "q", "customer_id": None}))
    assert out2["sql_success"] is False


def test_run_sql_no_db(monkeypatch):
    monkeypatch.setattr(sql_action, "get_db_session", _make_db_session_gen(None))

    out = asyncio.run(sql_action.run_sql({"message": "q"}))
    assert "Unable to obtain a database session" in out["errors"][0]


def test_run_hybrid_success_and_no_db(monkeypatch):
    # patch RetrievalAgent, SQLService, HybridRetrievalService
    class FakeRA:
        def __init__(self, similarity_top_k=5):
            pass

    class FakeSQLService:
        def __init__(self, session):
            pass

    class FakeHybrid:
        def __init__(self, rag_service, sql_service):
            pass

        async def run(self, query, customer_id=None, session=None):
            return {
                "rag_results": [{"title": "T"}],
                "rag_confidence": 0.7,
                "sufficient_evidence": True,
                "sql_result": {
                    "sql": "SELECT 1",
                    "rows": [{"a": 1}],
                    "row_count": 1,
                    "confidence": 0.8,
                    "success": True,
                },
                "evidence_summary": "sum",
                "errors": [],
            }

    monkeypatch.setattr(hybrid_action, "RetrievalAgent", FakeRA)
    monkeypatch.setattr(hybrid_action, "SQLService", FakeSQLService)
    monkeypatch.setattr(hybrid_action, "HybridRetrievalService", FakeHybrid)
    monkeypatch.setattr(
        hybrid_action, "get_db_session", _make_db_session_gen(SimpleNamespace())
    )

    out = asyncio.run(hybrid_action.run_hybrid({"message": "q", "customer_id": "cid"}))
    assert out["selected_action"] == "hybrid"
    assert out["sql_success"] is True

    # no db
    monkeypatch.setattr(hybrid_action, "get_db_session", _make_db_session_gen(None))
    out2 = asyncio.run(hybrid_action.run_hybrid({"message": "q"}))
    assert "Unable to obtain a database session" in out2["errors"][0]
