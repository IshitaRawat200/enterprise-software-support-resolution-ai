from types import SimpleNamespace

import pytest

from app.rag.loaders.document_loader import KnowledgeBaseDocumentLoader


def test_load_file_not_found(tmp_path):
    loader = KnowledgeBaseDocumentLoader()
    with pytest.raises(FileNotFoundError):
        loader.load_file(tmp_path / "nope.txt")


def test_load_file_unsupported_extension(tmp_path):
    p = tmp_path / "a.docx"
    p.write_text("x")
    loader = KnowledgeBaseDocumentLoader()
    with pytest.raises(ValueError):
        loader.load_file(p)


def test_load_file_text_sets_metadata(monkeypatch, tmp_path):
    p = tmp_path / "a.txt"
    p.write_text("content")

    loader = KnowledgeBaseDocumentLoader()

    # replace text loader
    monkeypatch.setattr(
        loader,
        "text_loader",
        SimpleNamespace(load=lambda path: [SimpleNamespace(metadata={})]),
    )

    docs = loader.load_file(p)
    assert docs[0].metadata["document_name"] == p.name
    assert docs[0].metadata["document_type"] == ".txt"


def test_load_directory_filters_and_raises(tmp_path):
    dirp = tmp_path / "d"
    dirp.mkdir()
    (dirp / "a.bin").write_text("x")

    loader = KnowledgeBaseDocumentLoader()
    with pytest.raises(ValueError):
        loader.load_directory(dirp)
