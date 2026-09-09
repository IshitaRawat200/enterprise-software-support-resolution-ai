import asyncio
import json
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest

from app.rag.database.rag_database_repository import RAGDatabaseRepository


class FakeResult:
    def __init__(self, first=None, scalar=None, mappings_list=None):
        self._first = first
        self._scalar = scalar
        self._mappings = mappings_list or []

    def first(self):
        return self._first

    def scalar_one(self):
        return self._scalar

    def mappings(self):
        return SimpleNamespace(all=lambda: self._mappings)


class FakeSession:
    def __init__(self):
        self.last_execute = None
        self.next_result = None

    async def execute(self, *args, **kwargs):
        self.last_execute = (args, kwargs)
        return self.next_result


def test_find_document_by_hash_found_and_none():
    fs = FakeSession()
    doc_id = uuid4()
    fs.next_result = FakeResult(first=(doc_id,))

    repo = RAGDatabaseRepository(session=fs)
    out = asyncio.run(repo.find_document_by_hash("hash1"))
    assert isinstance(out, UUID)

    fs.next_result = FakeResult(first=None)
    out2 = asyncio.run(repo.find_document_by_hash("nope"))
    assert out2 is None


def test_create_document_and_chunk_and_count_chunks():
    fs = FakeSession()
    fs.next_result = FakeResult()
    repo = RAGDatabaseRepository(session=fs)

    doc_id = asyncio.run(
        repo.create_document("name", "txt", None, None, None, None, "h", {"k": "v"})
    )
    assert isinstance(doc_id, UUID)

    fs.next_result = FakeResult()
    chunk_id = asyncio.run(
        repo.create_chunk(doc_id, 0, "content", 10, [0.1, 0.2], {"m": 1})
    )
    assert isinstance(chunk_id, UUID)

    fs.next_result = FakeResult(scalar=5)
    cnt = asyncio.run(repo.count_chunks(doc_id))
    assert cnt == 5


def test_list_chunks_limit_and_mappings():
    fs = FakeSession()
    # prepare mapping rows with metadata as JSON string
    sample_row = {
        "id": uuid4(),
        "document_id": uuid4(),
        "chunk_index": 0,
        "content": "c",
        "token_count": 10,
        "metadata": json.dumps({"foo": "bar"}),
        "document_name": "doc",
        "document_type": "md",
        "source_url": None,
        "product_name": None,
        "product_version": None,
        "version": None,
    }

    fs.next_result = FakeResult(mappings_list=[sample_row])
    repo = RAGDatabaseRepository(session=fs)
    chunks = asyncio.run(repo.list_chunks(limit=1))
    assert len(chunks) == 1
    assert chunks[0]["metadata"]["foo"] == "bar"

    with pytest.raises(ValueError):
        asyncio.run(repo.list_chunks(limit=0))
