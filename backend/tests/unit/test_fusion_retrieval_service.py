import asyncio
from types import SimpleNamespace

import pytest
from app.rag.services.fusion_retrieval_service import (
    FusionRetrievalService,
)


def test_constructor_validations():
    from app.rag.services.fusion_retrieval_service import FusionRetrievalService

    sess = SimpleNamespace()

    with pytest.raises(ValueError):
        FusionRetrievalService(sess, similarity_top_k=0)

    with pytest.raises(ValueError):
        FusionRetrievalService(sess, minimum_similarity=-0.1)


def test_create_fusion_llm_raises(monkeypatch):
    from app.rag.services import fusion_retrieval_service as frs

    monkeypatch.setattr(
        frs,
        "get_settings",
        lambda: SimpleNamespace(groq_api_key=None, groq_simple_model="m"),
    )

    from app.rag.services.fusion_retrieval_service import FusionRetrievalService

    svc = FusionRetrievalService(SimpleNamespace())

    with pytest.raises(RuntimeError):
        svc._create_fusion_llm()


@pytest.mark.asyncio
async def test_retrieve_evidence_filters_and_formats(monkeypatch):
    from app.rag.services.fusion_retrieval_service import FusionRetrievalService

    # Avoid initializing the real repository
    monkeypatch.setattr(
        "app.rag.services.fusion_retrieval_service.RAGDatabaseRepository",
        lambda session: SimpleNamespace(),
    )

    svc = FusionRetrievalService(SimpleNamespace())

    # fake fusion retriever returns one item
    node_meta = {"chunk_id": 123, "document_name": "doc.txt", "title": "T"}

    node = SimpleNamespace(metadata=node_meta, get_content=lambda: "the content")

    fusion_item = SimpleNamespace(node=node, score=0.5)

    class FakeFusion:
        async def aretrieve(self, q):
            return [fusion_item]

    # fake vector retriever returns a higher semantic score for the same chunk
    vec_item = SimpleNamespace(node=node, score=0.85)

    class FakeVector:
        async def aretrieve(self, q):
            return [vec_item]

    svc.fusion_retriever = FakeFusion()
    svc.vector_retriever = FakeVector()

    # set minimum similarity so 0.85 passes
    svc.minimum_similarity = 0.5

    results = await svc.retrieve_evidence("query")

    assert isinstance(results, list)
    assert len(results) == 1

    r = results[0]
    assert r["document_name"] == "doc.txt"
    assert r["vector_score"] == round(0.85, 4)
    assert r["rrf_score"] == round(0.5, 4)


def test_create_fusion_llm_raises_when_no_key(monkeypatch):
    # Force get_settings to return empty groq key
    monkeypatch.setattr(
        "app.rag.services.fusion_retrieval_service.get_settings",
        lambda: SimpleNamespace(groq_api_key="", groq_simple_model="m"),
    )

    svc = FusionRetrievalService(session=None)

    try:
        svc._create_fusion_llm()
    except RuntimeError as exc:
        assert "GROQ_API_KEY is not configured" in str(exc)


def test_build_retrieval_index_raises_when_no_chunks(monkeypatch):
    svc = FusionRetrievalService(session=None)

    class FakeRepo:
        async def list_chunks(self):
            return []

    svc.repository = FakeRepo()

    try:
        asyncio.run(svc._build_retrieval_index())
    except ValueError as exc:
        assert "No knowledge-base chunks are available" in str(exc)
