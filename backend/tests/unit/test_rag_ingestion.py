from types import SimpleNamespace

import pytest

from app.rag.ingestion import RAGDocumentIngestionService


def make_chunk(page_content="c", metadata=None):
    return SimpleNamespace(page_content=page_content, metadata=metadata or {})


def test_load_file_success(monkeypatch, tmp_path):
    svc = RAGDocumentIngestionService()

    # patch loader, processor, chunker
    monkeypatch.setattr(svc, "loader", SimpleNamespace(load_file=lambda p: ["doc"]))
    monkeypatch.setattr(
        svc, "processor", SimpleNamespace(process=lambda docs: ["processed"])
    )
    monkeypatch.setattr(
        svc,
        "chunker",
        SimpleNamespace(split_documents=lambda docs: [make_chunk("text", {"a": 1})]),
    )

    out = svc.load_file(str(tmp_path / "file.txt"))
    assert isinstance(out, list)
    assert out[0].text == "text"
    assert out[0].metadata.get("a") == 1


def test_load_file_no_chunks_raises(monkeypatch, tmp_path):
    svc = RAGDocumentIngestionService()
    monkeypatch.setattr(svc, "loader", SimpleNamespace(load_file=lambda p: ["doc"]))
    monkeypatch.setattr(
        svc, "processor", SimpleNamespace(process=lambda docs: ["processed"])
    )
    monkeypatch.setattr(
        svc, "chunker", SimpleNamespace(split_documents=lambda docs: [])
    )

    with pytest.raises(ValueError):
        svc.load_file(str(tmp_path / "file.txt"))


def test_load_directory_success(monkeypatch, tmp_path):
    dirp = tmp_path / "d"
    dirp.mkdir()

    # create two files
    f1 = dirp / "a.txt"
    f1.write_text("one")
    f2 = dirp / "b.md"
    f2.write_text("two")

    svc = RAGDocumentIngestionService()
    monkeypatch.setattr(
        svc,
        "loader",
        SimpleNamespace(
            load_directory=lambda p: ["doc1", "doc2"], load_file=lambda p: ["doc"]
        ),
    )
    monkeypatch.setattr(
        svc, "processor", SimpleNamespace(process=lambda docs: ["processed"])
    )
    monkeypatch.setattr(
        svc,
        "chunker",
        SimpleNamespace(split_documents=lambda docs: [make_chunk("page", {"b": 2})]),
    )

    out = svc.load_directory(str(dirp))
    assert len(out) == 1
    assert out[0].text == "page"


def test_load_directory_no_chunks_raises(monkeypatch, tmp_path):
    dirp = tmp_path / "d2"
    dirp.mkdir()
    (dirp / "a.txt").write_text("x")

    svc = RAGDocumentIngestionService()
    monkeypatch.setattr(
        svc, "loader", SimpleNamespace(load_directory=lambda p: ["doc"])
    )
    monkeypatch.setattr(
        svc, "processor", SimpleNamespace(process=lambda docs: ["processed"])
    )
    monkeypatch.setattr(
        svc, "chunker", SimpleNamespace(split_documents=lambda docs: [])
    )

    with pytest.raises(ValueError):
        svc.load_directory(str(dirp))
