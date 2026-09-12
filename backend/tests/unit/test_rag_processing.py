import pytest
from langchain_core.documents import Document


def test_document_parser_success(tmp_path):
    from app.rag.parser import DocumentParser

    f = tmp_path / "notes.txt"
    f.write_text("  hello world  ", encoding="utf-8")

    parser = DocumentParser()
    text = parser.parse(f)

    assert text == "hello world"


def test_document_parser_file_not_found():
    from app.rag.parser import DocumentParser

    parser = DocumentParser()

    with pytest.raises(FileNotFoundError):
        parser.parse("/no/such/file.txt")


def test_document_parser_not_file(tmp_path):
    from app.rag.parser import DocumentParser

    d = tmp_path / "dir"
    d.mkdir()

    parser = DocumentParser()

    with pytest.raises(ValueError):
        parser.parse(d)


def test_document_parser_unsupported_extension(tmp_path):
    from app.rag.parser import DocumentParser

    f = tmp_path / "data.pdf"
    f.write_text("x")

    parser = DocumentParser()

    with pytest.raises(ValueError):
        parser.parse(f)


def test_document_parser_empty_content(tmp_path):
    from app.rag.parser import DocumentParser

    f = tmp_path / "empty.txt"
    f.write_text("   \n  ")

    parser = DocumentParser()

    with pytest.raises(ValueError):
        parser.parse(f)


def test_processing_service_filters_and_defaults():
    from app.rag.processing.document_processing_service import DocumentProcessingService

    docs = [
        Document(page_content="  a b c  ", metadata={}),
        Document(page_content="   ", metadata={}),
        Document(
            page_content="ok", metadata={"document_name": "n", "document_type": ".md"}
        ),
    ]

    svc = DocumentProcessingService()
    out = svc.process(docs)

    assert len(out) == 2
    assert out[0].page_content == "a b c"
    assert out[0].metadata["document_name"] == "unknown"
    assert out[1].metadata["document_name"] == "n"


def test_processing_preserves_metadata_keys():
    from app.rag.processing.document_processing_service import DocumentProcessingService

    docs = [Document(page_content="x", metadata={"foo": "bar"})]

    svc = DocumentProcessingService()
    out = svc.process(docs)

    assert out[0].metadata["foo"] == "bar"
