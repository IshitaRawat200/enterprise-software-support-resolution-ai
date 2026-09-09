import asyncio
from types import SimpleNamespace

import pytest

from app.rag.services.fusion_retrieval_service import FusionRetrievalService


def test_create_fusion_llm_missing_key(monkeypatch):
    # No GROQ API key should raise
    monkeypatch.setattr(
        "app.rag.services.fusion_retrieval_service.get_settings",
        lambda: SimpleNamespace(groq_api_key=None, groq_simple_model="m"),
    )

    with pytest.raises(RuntimeError):
        FusionRetrievalService._create_fusion_llm()


def test_build_retrieval_index_no_chunks(monkeypatch):
    svc = FusionRetrievalService(session=SimpleNamespace(), similarity_top_k=5)

    async def fake_list_chunks():
        return []

    svc.repository = SimpleNamespace(list_chunks=fake_list_chunks)

    with pytest.raises(ValueError):
        asyncio.run(svc._build_retrieval_index())


def test_retrieve_vector_results_scores(monkeypatch):
    svc = FusionRetrievalService(session=SimpleNamespace(), similarity_top_k=5)

    class FakeNode:
        def __init__(self, content, metadata=None):
            self.metadata = metadata or {}
            self._content = content

        def get_content(self):
            return self._content

    class FakeItem:
        def __init__(self, node, score):
            self.node = node
            self.score = score

    async def fake_aretrieve(query):
        n1 = FakeNode("a", {"chunk_id": "c1"})
        n2 = FakeNode("b", {"chunk_id": "c1"})
        return [FakeItem(n1, 0.3), FakeItem(n2, 0.7)]

    svc.vector_retriever = SimpleNamespace(aretrieve=fake_aretrieve)

    scores = asyncio.run(svc._retrieve_vector_results("q"))
    assert scores.get("c1") == pytest.approx(0.7)


def test_build_retrieval_index_success(monkeypatch):
    svc = FusionRetrievalService(session=SimpleNamespace(), similarity_top_k=5)

    # fake chunks
    async def fake_list_chunks():
        return [
            {
                "content": " doc1 ",
                "metadata": {"chunk_id": "c1", "document_id": "d1", "title": "T1"},
            },
            {"content": " doc2 ", "metadata": {"chunk_id": "c2", "document_id": "d1"}},
        ]

    svc.repository = SimpleNamespace(list_chunks=fake_list_chunks)

    # fake Settings.embed_model assignment allowed
    # fake VectorStoreIndex.from_documents
    class FakeIndex:
        def __init__(self, docs):
            self.docstore = SimpleNamespace(docs={"n1": SimpleNamespace()})

        def as_retriever(self, similarity_top_k):
            return SimpleNamespace()

    monkeypatch.setattr(
        "app.rag.services.fusion_retrieval_service.VectorStoreIndex",
        SimpleNamespace(from_documents=lambda docs: FakeIndex(docs)),
    )

    # fake BM25Retriever
    monkeypatch.setattr(
        "app.rag.services.fusion_retrieval_service.BM25Retriever",
        SimpleNamespace(
            from_defaults=lambda nodes, similarity_top_k: SimpleNamespace()
        ),
    )

    # fake fusion retriever factory
    monkeypatch.setattr(
        "app.rag.services.fusion_retrieval_service.QueryFusionRetriever",
        lambda **kwargs: SimpleNamespace(),
    )

    # patch _create_fusion_llm to avoid real Groq
    monkeypatch.setattr(
        FusionRetrievalService,
        "_create_fusion_llm",
        staticmethod(lambda: SimpleNamespace()),
    )

    asyncio.run(svc._build_retrieval_index())

    assert svc.vector_index is not None
    assert svc.vector_retriever is not None
    assert svc.bm25_retriever is not None
    assert svc.fusion_retriever is not None
