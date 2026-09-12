from types import SimpleNamespace

import pytest


def test_text_loader_success(tmp_path, monkeypatch):
    from app.rag.loaders.text_loader import TextDocumentLoader

    file = tmp_path / "doc.txt"
    file.write_text("hello world", encoding="utf-8")

    class FakeLoader:
        def __init__(self, path, encoding=None):
            self.path = path
            self.encoding = encoding

        def load(self):
            return [SimpleNamespace(metadata={"source": str(self.path)})]

    monkeypatch.setattr("app.rag.loaders.text_loader.TextLoader", FakeLoader)

    loader = TextDocumentLoader()
    docs = loader.load(file)

    assert isinstance(docs, list)
    assert docs[0].metadata["source"].endswith("doc.txt")


def test_text_loader_file_not_found():
    from app.rag.loaders.text_loader import TextDocumentLoader

    loader = TextDocumentLoader()

    with pytest.raises(FileNotFoundError):
        loader.load("/non/existent/file.txt")


def test_text_loader_not_file(tmp_path):
    from app.rag.loaders.text_loader import TextDocumentLoader

    folder = tmp_path / "folder"
    folder.mkdir()

    loader = TextDocumentLoader()

    with pytest.raises(ValueError):
        loader.load(folder)


def test_text_loader_unsupported_extension(tmp_path):
    from app.rag.loaders.text_loader import TextDocumentLoader

    file = tmp_path / "data.bin"
    file.write_text("binary-ish")

    loader = TextDocumentLoader()

    with pytest.raises(ValueError):
        loader.load(file)


def test_html_loader_success(tmp_path, monkeypatch):
    from app.rag.loaders.html_loader import HTMLDocumentLoader

    file = tmp_path / "page.html"
    file.write_text("<p>ok</p>")

    class FakeLoader:
        def __init__(self, path):
            self.path = path

        def load(self):
            return [SimpleNamespace(metadata={"source": str(self.path)})]

    monkeypatch.setattr(
        "app.rag.loaders.html_loader.UnstructuredHTMLLoader", FakeLoader
    )

    loader = HTMLDocumentLoader()
    docs = loader.load(file)

    assert docs[0].metadata["source"].endswith("page.html")


def test_pdf_loader_success(tmp_path, monkeypatch):
    from app.rag.loaders.pdf_loader import PDFDocumentLoader

    file = tmp_path / "doc.pdf"
    # content doesn't matter for the fake loader
    file.write_bytes(b"%PDF-1.4\n")

    class FakeLoader:
        def __init__(self, path):
            self.path = path

        def load(self):
            return [SimpleNamespace(metadata={"source": str(self.path)})]

    monkeypatch.setattr("app.rag.loaders.pdf_loader.PyPDFLoader", FakeLoader)

    loader = PDFDocumentLoader()
    docs = loader.load(file)

    assert docs[0].metadata["source"].endswith("doc.pdf")
