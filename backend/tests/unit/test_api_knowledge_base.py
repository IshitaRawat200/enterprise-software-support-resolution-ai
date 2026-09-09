import io
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

import app.api.knowledge_base as kb


class DummySession:
    pass


class FakeService:
    def __init__(self, session):
        self._session = session

    async def ingest_file(self, path, original_filename=None):
        return {"ok": True, "file": original_filename}


async def _agen_single(y):
    if False:
        yield None
    yield y


def make_upload_file(filename: str, content_type: str, data: bytes):
    f = SimpleNamespace()
    f.filename = filename
    f.content_type = content_type
    f.file = io.BytesIO(data)
    return f


def test_upload_no_filename():
    f = make_upload_file("", "application/pdf", b"x")

    with pytest.raises(HTTPException) as exc:
        import asyncio

        asyncio.run(
            kb.upload_knowledge_document(file=f, current_user=SimpleNamespace())
        )

    assert exc.value.status_code == 400


def test_upload_unsupported_extension():
    f = make_upload_file("bad.exe", "application/pdf", b"x")

    with pytest.raises(HTTPException) as exc:
        import asyncio

        asyncio.run(
            kb.upload_knowledge_document(file=f, current_user=SimpleNamespace())
        )

    assert exc.value.status_code == 400


def test_upload_unsupported_content_type():
    f = make_upload_file("doc.pdf", "application/octet-stream", b"x")

    with pytest.raises(HTTPException) as exc:
        import asyncio

        asyncio.run(
            kb.upload_knowledge_document(file=f, current_user=SimpleNamespace())
        )

    assert exc.value.status_code == 400


def test_upload_success(monkeypatch, tmp_path):
    f = make_upload_file("doc.pdf", "application/pdf", b"hello")

    async def fake_get_db_session():
        async for x in _agen_single(DummySession()):
            yield x

    monkeypatch.setattr(kb, "get_db_session", fake_get_db_session)
    monkeypatch.setattr(kb, "DBRAGIngestionService", FakeService)

    import asyncio

    out = asyncio.run(
        kb.upload_knowledge_document(file=f, current_user=SimpleNamespace())
    )

    assert out["message"].startswith("Knowledge document processed")
    assert out["filename"] == "doc.pdf"
    assert out["result"]["ok"] is True


def test_upload_ingest_value_error(monkeypatch):
    f = make_upload_file("doc.pdf", "application/pdf", b"hello")

    class BadService:
        def __init__(self, session):
            pass

        async def ingest_file(self, path, original_filename=None):
            raise ValueError("bad file")

    async def fake_get_db_session():
        async for x in _agen_single(DummySession()):
            yield x

    monkeypatch.setattr(kb, "get_db_session", fake_get_db_session)
    monkeypatch.setattr(kb, "DBRAGIngestionService", BadService)

    import asyncio

    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            kb.upload_knowledge_document(file=f, current_user=SimpleNamespace())
        )

    assert exc.value.status_code == 400


def test_upload_ingest_db_error(monkeypatch):
    from sqlalchemy.exc import SQLAlchemyError

    f = make_upload_file("doc.pdf", "application/pdf", b"hello")

    class BadService:
        def __init__(self, session):
            pass

        async def ingest_file(self, path, original_filename=None):
            raise SQLAlchemyError("boom")

    async def fake_get_db_session():
        async for x in _agen_single(DummySession()):
            yield x

    monkeypatch.setattr(kb, "get_db_session", fake_get_db_session)
    monkeypatch.setattr(kb, "DBRAGIngestionService", BadService)

    import asyncio

    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            kb.upload_knowledge_document(file=f, current_user=SimpleNamespace())
        )

    assert exc.value.status_code == 500
