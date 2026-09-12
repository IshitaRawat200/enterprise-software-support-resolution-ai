from types import SimpleNamespace

import pytest


def make_fake_doc(name):
    return SimpleNamespace(metadata={"title": name})


def test_load_file_text_routes_and_metadata(monkeypatch, tmp_path):
    from app.rag.loaders import document_loader
    from app.rag.loaders.document_loader import KnowledgeBaseDocumentLoader

    txt = tmp_path / "notes.txt"
    txt.write_text("note")

    class FakeTextLoader:
        def load(self, path):
            return [make_fake_doc("t1")]

    monkeypatch.setattr(document_loader, "TextDocumentLoader", FakeTextLoader)

    loader = KnowledgeBaseDocumentLoader()
    docs = loader.load_file(txt)

    assert len(docs) == 1
    assert docs[0].metadata["document_name"] == "notes.txt"
    assert docs[0].metadata["document_type"] == ".txt"


def test_load_file_pdf_and_html_routing(monkeypatch, tmp_path):
    from app.rag.loaders import document_loader
    from app.rag.loaders.document_loader import KnowledgeBaseDocumentLoader

    pdf = tmp_path / "report.pdf"
    pdf.write_bytes(b"%PDF")

    html = tmp_path / "page.html"
    html.write_text("<p>x</p>")

    class FakePDFLoader:
        def load(self, path):
            return [make_fake_doc("p1")]

    class FakeHTMLLoader:
        def load(self, path):
            return [make_fake_doc("h1")]

    monkeypatch.setattr(document_loader, "PDFDocumentLoader", FakePDFLoader)
    monkeypatch.setattr(document_loader, "HTMLDocumentLoader", FakeHTMLLoader)

    loader = KnowledgeBaseDocumentLoader()

    pdf_docs = loader.load_file(pdf)
    html_docs = loader.load_file(html)

    assert pdf_docs[0].metadata["document_type"] == ".pdf"
    assert html_docs[0].metadata["document_type"] == ".html"


def test_load_directory_filters_and_errors(monkeypatch, tmp_path):
    from app.rag.loaders import document_loader
    from app.rag.loaders.document_loader import KnowledgeBaseDocumentLoader

    # create supported and unsupported files
    (tmp_path / "a.txt").write_text("1")
    (tmp_path / "b.bin").write_text("2")

    class FakeTextLoader:
        def load(self, path):
            return [make_fake_doc("d")]

    monkeypatch.setattr(document_loader, "TextDocumentLoader", FakeTextLoader)

    loader = KnowledgeBaseDocumentLoader()

    docs = loader.load_directory(tmp_path)
    assert len(docs) == 1

    # directory exists but contains no supported documents
    other = tmp_path / "empty_dir"
    other.mkdir()
    with pytest.raises(ValueError):
        loader.load_directory(other)


def test_load_file_errors(tmp_path):
    from app.rag.loaders.document_loader import KnowledgeBaseDocumentLoader

    loader = KnowledgeBaseDocumentLoader()

    with pytest.raises(FileNotFoundError):
        loader.load_file("/no/such/file.md")

    bad = tmp_path / "file.bin"
    bad.write_text("x")
    with pytest.raises(ValueError):
        loader.load_file(bad)
