import asyncio
from types import SimpleNamespace

import pytest
from langchain_core.documents import Document

import app.rag.chunking as chunking_mod
import app.rag.embeddings as emb_mod
from app.sql.sql_service import SQLService


def test_chunker_validation_and_split():
    # invalid params
    with pytest.raises(ValueError):
        chunking_mod.DocumentChunker(chunk_size=0)

    with pytest.raises(ValueError):
        chunking_mod.DocumentChunker(chunk_size=10, chunk_overlap=20)

    chunker = chunking_mod.DocumentChunker(chunk_size=5, chunk_overlap=1)
    docs = [
        Document(page_content="This is a test document. It has sentences.", metadata={})
    ]
    chunks = chunker.split_documents(docs)
    assert isinstance(chunks, list)
    assert all(isinstance(c, Document) for c in chunks)


def test_embeddings_service_monkeypatched(monkeypatch):
    class FakeModel:
        def encode(self, text, normalize_embeddings=True):
            class Arr:
                def __init__(self):
                    self._v = [0.0] * emb_mod.RAGEmbeddingService.EMBEDDING_DIMENSION

                def tolist(self):
                    return self._v

            return Arr()

    monkeypatch.setattr(emb_mod, "get_embedding_model", lambda: FakeModel())

    svc = emb_mod.RAGEmbeddingService()
    v = svc.embed_query("hello")
    assert len(v) == emb_mod.RAGEmbeddingService.EMBEDDING_DIMENSION

    v2 = svc.embed_document("doc")
    assert len(v2) == emb_mod.RAGEmbeddingService.EMBEDDING_DIMENSION


def test_sql_service_guardrail_block(monkeypatch):
    class FakeGeneration:
        sql = "SELECT 1"
        confidence = 0.5
        explanation = "explain"
        tables_used = ("tickets",)

    async def fake_generate(self, question, customer_id=None):
        return FakeGeneration()

    monkeypatch.setattr("app.sql.sql_generator.SQLGenerator.generate", fake_generate)

    # guardrail blocks
    monkeypatch.setattr(
        "app.guardrails.guardrails_service.guardrails_service.validate_sql",
        lambda sql: SimpleNamespace(
            allowed=False, reason="blocked", guardrail_name="g", code="C", risk_level=5
        ),
    )

    svc = SQLService(session=SimpleNamespace())
    out = asyncio.run(svc.query("q", customer_id=None))
    assert out["guardrail_blocked"] is True


def test_sql_service_execute(monkeypatch):
    class FakeGeneration:
        sql = "SELECT 1"
        confidence = 0.5
        explanation = "explain"
        tables_used = ("tickets",)

    async def fake_generate(self, question, customer_id=None):
        return FakeGeneration()

    async def fake_execute(self, sql):
        return {
            "success": True,
            "sql": sql,
            "rows": [{"a": 1}],
            "row_count": 1,
            "error": None,
        }

    monkeypatch.setattr("app.sql.sql_generator.SQLGenerator.generate", fake_generate)
    monkeypatch.setattr(
        "app.guardrails.guardrails_service.guardrails_service.validate_sql",
        lambda sql: SimpleNamespace(
            allowed=True, reason="ok", guardrail_name="g", code="C", risk_level=1
        ),
    )
    monkeypatch.setattr("app.sql.sql_executor.SQLExecutor.execute", fake_execute)

    svc = SQLService(session=SimpleNamespace())
    out = asyncio.run(svc.query("q", customer_id="cid"))
    assert out["success"] is True
    assert out["row_count"] == 1
