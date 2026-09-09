import asyncio
from types import SimpleNamespace

from app.orchestrator import graph as orchestrator_graph
from app.orchestrator.actions import hybrid_action, rag_action, sql_action


async def _agen_single(x):
    if False:
        yield None
    yield x


def test_build_uncheckpointed_graph():
    g = orchestrator_graph.build_uncheckpointed_graph()
    assert g is not None


def test_run_rag_success(monkeypatch):
    # fake retrieval agent run
    class FakeRetrieval:
        async def run(self, query, session=None):
            return {
                "results": [{"id": 1}],
                "confidence": 0.6,
                "sufficient_evidence": True,
                "reason": "ok",
            }

    monkeypatch.setattr(
        rag_action, "RetrievalAgent", lambda similarity_top_k: FakeRetrieval()
    )

    async def fake_get_db_session():
        async for s in _agen_single(SimpleNamespace()):
            yield s

    monkeypatch.setattr(rag_action, "get_db_session", fake_get_db_session)

    out = asyncio.run(rag_action.run_rag({"message": "query"}))
    assert out["selected_action"] == "documentation_retrieval"
    assert out["retrieval_confidence"] == 0.6


def test_run_rag_no_db(monkeypatch):
    async def fake_get_db_session():
        if False:
            yield None

    monkeypatch.setattr(rag_action, "get_db_session", fake_get_db_session)

    out = asyncio.run(rag_action.run_rag({"message": "query"}))
    assert out["errors"]


def test_run_sql_success(monkeypatch):
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
            }

    async def fake_get_db_session():
        async for s in _agen_single(SimpleNamespace()):
            yield s

    monkeypatch.setattr(sql_action, "get_db_session", fake_get_db_session)
    monkeypatch.setattr(sql_action, "SQLService", FakeSQLService)

    out = asyncio.run(sql_action.run_sql({"message": "q", "customer_id": "cid"}))
    assert out["sql_success"] is True
    assert out["sql_row_count"] == 1


def test_run_sql_failure(monkeypatch):
    class FakeSQLService:
        def __init__(self, session):
            pass

        async def query(self, question, customer_id=None):
            return {
                "success": False,
                "sql": "SELECT 1",
                "error": "fail",
                "sql_confidence": 0.2,
            }

    async def fake_get_db_session():
        async for s in _agen_single(SimpleNamespace()):
            yield s

    monkeypatch.setattr(sql_action, "get_db_session", fake_get_db_session)
    monkeypatch.setattr(sql_action, "SQLService", FakeSQLService)

    out = asyncio.run(sql_action.run_sql({"message": "q", "customer_id": None}))
    assert out["sql_success"] is False


def test_run_hybrid_success(monkeypatch):
    class FakeHybridService:
        async def run(self, query, customer_id=None, session=None):
            return {
                "rag_results": [{"id": 1}],
                "rag_confidence": 0.7,
                "sufficient_evidence": True,
                "sql_result": {"success": True, "rows": [{"x": 1}], "confidence": 0.8},
                "hybrid_confidence": 0.75,
                "evidence_summary": "ok",
            }

    async def fake_get_db_session():
        async for s in _agen_single(SimpleNamespace()):
            yield s

    monkeypatch.setattr(hybrid_action, "get_db_session", fake_get_db_session)
    monkeypatch.setattr(
        hybrid_action, "HybridRetrievalService", lambda **kw: FakeHybridService()
    )
    monkeypatch.setattr(
        hybrid_action, "RetrievalAgent", lambda similarity_top_k: SimpleNamespace()
    )
    monkeypatch.setattr(hybrid_action, "SQLService", lambda session: SimpleNamespace())

    out = asyncio.run(hybrid_action.run_hybrid({"message": "q", "customer_id": "cid"}))
    assert out["selected_action"] == "hybrid"
    assert out["hybrid_confidence"] == 0.75


def test_run_hybrid_no_db(monkeypatch):
    async def fake_get_db_session():
        if False:
            yield None

    monkeypatch.setattr(hybrid_action, "get_db_session", fake_get_db_session)
    out = asyncio.run(hybrid_action.run_hybrid({"message": "q", "customer_id": None}))
    assert out["hybrid_success"] is False
