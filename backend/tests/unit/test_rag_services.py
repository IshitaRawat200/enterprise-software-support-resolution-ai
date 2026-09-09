import asyncio
from types import SimpleNamespace

import pytest

from app.rag.services.db_rag_ingestion_service import DBRAGIngestionService
from app.rag.services.fusion_retrieval_service import FusionRetrievalService


def test_fusion_retrieval_empty_query_raises():
    svc = FusionRetrievalService(session=SimpleNamespace(), similarity_top_k=5)
    with pytest.raises(ValueError):
        asyncio.run(svc.retrieve(""))


def test_retrieve_evidence_process(monkeypatch):
    svc = FusionRetrievalService(session=SimpleNamespace(), similarity_top_k=5)

    # fake fusion results: items with node and score
    class FakeNode:
        def __init__(self, content, metadata):
            self._content = content
            self.metadata = metadata

        def get_content(self):
            return self._content

    class FakeItem:
        def __init__(self, node, score):
            self.node = node
            self.score = score

    fake_node = FakeNode(
        "doc text", {"chunk_id": "c1", "document_name": "doc.pdf", "title": "Doc"}
    )
    fake_item = FakeItem(fake_node, 0.8)

    # patch retrieve to return our fake items
    monkeypatch.setattr(
        FusionRetrievalService, "retrieve", lambda self, q: asyncio.Future()
    )

    # set actual future result via binding
    async def fake_retrieve(self, q):
        return [fake_item]

    monkeypatch.setattr(FusionRetrievalService, "retrieve", fake_retrieve)

    # patch vector results
    async def fake_vector_results(self, q):
        return {"c1": 0.9}

    monkeypatch.setattr(
        FusionRetrievalService, "_retrieve_vector_results", fake_vector_results
    )

    # ensure fusion_retriever is not required because we patched retrieve
    out = asyncio.run(svc.retrieve_evidence("query text"))
    assert isinstance(out, list)
    assert out and out[0]["document_name"] == "doc.pdf"


def test_dbrag_ingest_file_not_found(tmp_path):
    svc = DBRAGIngestionService(session=SimpleNamespace())
    with pytest.raises(FileNotFoundError):
        asyncio.run(svc.ingest_file(str(tmp_path / "nope.pdf")))


def test_dbrag_ingest_file_already_exists(tmp_path, monkeypatch):
    # create a small temp file
    p = tmp_path / "test.pdf"
    p.write_bytes(b"hello world")

    session = SimpleNamespace()
    svc = DBRAGIngestionService(session=session)

    # fake repository find by hash

    class FakeRepo:
        def __init__(self):
            pass

        async def find_document_by_hash(self, h):
            return 123

        async def count_chunks(self, doc_id):
            return 7

    monkeypatch.setattr(svc, "repository", FakeRepo())

    out = asyncio.run(svc.ingest_file(str(p), original_filename="orig.pdf"))
    assert out["status"] == "already_exists"
    assert out["chunks_created"] == 7


def test_dbrag_ingest_file_success(tmp_path, monkeypatch):
    p = tmp_path / "doc.txt"
    p.write_text("one two three")

    session = SimpleNamespace()

    # async commit/rollback
    async def acommit():
        return None

    async def arollback():
        return None

    session.commit = acommit
    session.rollback = arollback

    svc = DBRAGIngestionService(session=session)

    # fake repository with create_document and create_chunk
    class FakeRepo:
        async def find_document_by_hash(self, h):
            return None

        async def create_document(self, **kwargs):
            return 321

        async def create_chunk(self, **kwargs):
            return 1

    monkeypatch.setattr(svc, "repository", FakeRepo())

    # fake ingestion service to return documents with .text and .metadata
    class Doc:
        def __init__(self, text, metadata):
            self.text = text
            self.metadata = metadata

    monkeypatch.setattr(
        svc.ingestion_service,
        "load_file",
        lambda file_path, metadata=None: [Doc("one two three", {"source_url": "u"})],
    )

    # patch embedding to deterministic vector
    monkeypatch.setattr(
        svc.embedding_service,
        "embed_document",
        lambda text: [0.0] * svc.embedding_service.EMBEDDING_DIMENSION,
    )

    out = asyncio.run(svc.ingest_file(str(p), original_filename="orig.txt"))
    assert out["status"] == "indexed"
    assert out["chunks_created"] == 1
