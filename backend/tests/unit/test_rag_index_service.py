from types import SimpleNamespace
from pathlib import Path
import pytest

# Ensure compatibility with older embedding API name: create_embedding_model
import importlib

emb_mod = importlib.import_module("app.rag.embeddings")
# During tests, avoid loading heavy HF models — expose a no-op creator.
setattr(emb_mod, "create_embedding_model", lambda: None)


def test_build_requires_documents(tmp_path):
    from app.rag.services.rag_index_service import RAGIndexService

    svc = RAGIndexService(tmp_path / "idx")

    with pytest.raises(ValueError):
        svc.build([])


def test_build_persists_index(tmp_path, monkeypatch):
    from app.rag.services import rag_index_service as ris
    from app.rag.services.rag_index_service import RAGIndexService

    recorded = {}

    class FakeStorageContext:
        def __init__(self):
            pass

        def persist(self, persist_dir=None):
            recorded["persisted"] = persist_dir

    class FakeIndex:
        def __init__(self):
            self.storage_context = FakeStorageContext()

    monkeypatch.setattr(
        ris,
        "VectorStoreIndex",
        SimpleNamespace(from_documents=lambda docs: FakeIndex()),
    )

    svc = RAGIndexService(tmp_path / "myindex")

    docs = [SimpleNamespace(text="x", metadata={})]

    idx = svc.build(docs)

    assert isinstance(idx, FakeIndex)
    assert Path(recorded["persisted"]).exists() or recorded["persisted"] is not None


def test_exists_and_load(monkeypatch, tmp_path):
    from app.rag.services import rag_index_service as ris
    from app.rag.services.rag_index_service import RAGIndexService

    idx_dir = tmp_path / "idxdir"

    svc = RAGIndexService(idx_dir)

    # initially does not exist
    assert not svc.exists()

    # create dir and test exists
    idx_dir.mkdir()
    assert svc.exists()

    # monkeypatch StorageContext.from_defaults and load_index_from_storage
    monkeypatch.setattr(
        ris, "StorageContext", SimpleNamespace(from_defaults=lambda persist_dir: "ctx")
    )
    monkeypatch.setattr(ris, "load_index_from_storage", lambda ctx: "loaded")

    loaded = svc.load()

    assert loaded == "loaded"


def test_configure_embeddings_calls_create(monkeypatch):
    from app.rag.services import rag_index_service as ris

    called = {}

    def fake_create():
        called["ok"] = True
        return None

    monkeypatch.setattr(ris, "create_embedding_model", fake_create)

    # calling static method should set Settings.embed_model via _configure_embeddings
    from app.rag.services.rag_index_service import RAGIndexService

    RAGIndexService._configure_embeddings()

    assert called.get("ok") is True
