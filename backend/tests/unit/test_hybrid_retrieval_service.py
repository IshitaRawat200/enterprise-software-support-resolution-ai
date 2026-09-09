import asyncio

import pytest

from app.hybrid.hybrid_retrieval_service import HybridRetrievalService


def test_retrieve_rag_run_interface(monkeypatch):
    class FakeRA:
        async def run(self, query, session=None):
            return {
                "results": [{"title": "Doc", "vector_score": 0.6, "rrf_score": 0.2}]
            }

    svc = HybridRetrievalService(rag_service=FakeRA())
    evidence, conf = asyncio.run(svc.retrieve_rag("q"))
    assert len(evidence) == 1
    assert conf == pytest.approx(0.6)


def test_retrieve_rag_retrieve_evidence_interface(monkeypatch):
    class FakeRA2:
        async def retrieve_evidence(self, q):
            return [{"title": "D2", "vector_score": 0.3}]

    svc = HybridRetrievalService(rag_service=FakeRA2())
    evidence, conf = asyncio.run(svc.retrieve_rag("q"))
    assert len(evidence) == 1
    assert conf == pytest.approx(0.3)


def test_retrieve_rag_skips_non_dicts():
    class FakeRA3:
        async def run(self, query, session=None):
            return {"results": ["notadict", {"title": "Good", "vector_score": 0.4}]}

    svc = HybridRetrievalService(rag_service=FakeRA3())
    evidence, conf = asyncio.run(svc.retrieve_rag("q"))
    assert len(evidence) == 1
    assert conf == pytest.approx(0.4)


def test_retrieve_rag_unsupported_interface_raises():
    class BadRA:
        pass

    svc = HybridRetrievalService(rag_service=BadRA())
    with pytest.raises(RuntimeError):
        asyncio.run(svc.retrieve_rag("q"))


def test_retrieve_sql_run_and_query_interfaces():
    class FakeSQLRun:
        async def run(self, query, customer_id=None):
            return {
                "sql": "SELECT 1",
                "rows": [{"a": 1}],
                "row_count": 1,
                "confidence": 0.8,
                "success": True,
            }

    svc = HybridRetrievalService(sql_service=FakeSQLRun())
    sql_e = asyncio.run(svc.retrieve_sql("q"))
    assert sql_e.success is True
    assert sql_e.confidence == pytest.approx(0.8)

    class FakeSQLQuery:
        async def query(self, question, customer_id=None):
            return None

    svc2 = HybridRetrievalService(sql_service=FakeSQLQuery())
    sql_e2 = asyncio.run(svc2.retrieve_sql("q"))
    assert sql_e2.success is False
    assert "no result" in sql_e2.validation_message.lower()


def test_calculate_hybrid_confidence_and_summary():
    svc = HybridRetrievalService()
    # both with high agreement bonus
    c = svc.calculate_hybrid_confidence(0.8, 0.8, True, True)
    assert c == pytest.approx(0.9)

    # rag only
    c2 = svc.calculate_hybrid_confidence(0.7, 0.0, True, False)
    assert c2 == pytest.approx(0.7)

    # sql only
    c3 = svc.calculate_hybrid_confidence(0.0, 0.6, False, True)
    assert c3 == pytest.approx(0.6)

    # build summary
    from app.hybrid.hybrid_retrieval_schema import HybridSQLEvidence

    summary = svc.build_evidence_summary([], None)
    assert "No relevant documentation" in summary

    sql_e = HybridSQLEvidence(
        success=True, confidence=0.5, row_count=2, rows=[{"a": 1}], sql_query="SELECT 1"
    )
    summary2 = svc.build_evidence_summary([], sql_e)
    assert "SQL validation returned 2 row(s)" in summary2


def test_run_hybrid_combines_and_errors():
    class FakeRA:
        async def run(self, query, session=None):
            return {"results": [{"title": "Doc", "vector_score": 0.7}]}

    class FakeSQL:
        async def run(self, query, customer_id=None):
            return {
                "rows": [{"x": 1}],
                "row_count": 1,
                "confidence": 0.75,
                "success": True,
            }

    svc = HybridRetrievalService(rag_service=FakeRA(), sql_service=FakeSQL())
    res = asyncio.run(svc.run("hello", customer_id="c"))
    assert res.hybrid_confidence > 0
    assert res.sufficient_evidence in {True, False}
