from __future__ import annotations

from pathlib import Path
from typing import Any

from langchain_core.documents import Document as LangChainDocument

from app.rag.loaders.html_loader import HTMLDocumentLoader
from app.rag.loaders.pdf_loader import PDFDocumentLoader
from app.rag.loaders.text_loader import TextDocumentLoader


class KnowledgeBaseDocumentLoader:
    """
    Routes knowledge-base files to the correct loader.

    Supported:
        .txt
        .md
        .pdf
        .html
        .htm
    """

    SUPPORTED_EXTENSIONS = {
        ".txt",
        ".md",
        ".pdf",
        ".html",
        ".htm",
    }

    def __init__(self) -> None:
        self.text_loader = TextDocumentLoader()
        self.pdf_loader = PDFDocumentLoader()
        self.html_loader = HTMLDocumentLoader()

    def load_file(
        self,
        file_path: str | Path,
    ) -> list[LangChainDocument]:

        path = Path(file_path)

        if not path.exists():
            raise FileNotFoundError(
                f"Document not found: {path}"
            )

        extension = path.suffix.lower()

        if extension not in self.SUPPORTED_EXTENSIONS:
            raise ValueError(
                f"Unsupported document type: {extension}. "
                f"Supported types: "
                f"{sorted(self.SUPPORTED_EXTENSIONS)}"
            )

        if extension in {".txt", ".md"}:
            documents = self.text_loader.load(path)

        elif extension == ".pdf":
            documents = self.pdf_loader.load(path)

        elif extension in {".html", ".htm"}:
            documents = self.html_loader.load(path)

        else:
            raise ValueError(
                f"No loader configured for {extension}"
            )

        for document in documents:
            document.metadata = {
                **document.metadata,
                "document_name": path.name,
                "document_type": extension,
                "file_path": str(path),
            }

        return documents

    def load_directory(
        self,
        directory_path: str | Path,
    ) -> list[LangChainDocument]:

        directory = Path(directory_path)

        if not directory.exists():
            raise FileNotFoundError(
                f"Knowledge-base directory not found: "
                f"{directory}"
            )

        if not directory.is_dir():
            raise ValueError(
                f"Path is not a directory: {directory}"
            )

        documents: list[LangChainDocument] = []

        for file_path in sorted(directory.iterdir()):

            if not file_path.is_file():
                continue

            if file_path.suffix.lower() not in self.SUPPORTED_EXTENSIONS:
                continue

            loaded_documents = self.load_file(
                file_path
            )

            documents.extend(
                loaded_documents
            )

        if not documents:
            raise ValueError(
                f"No supported documents found in "
                f"{directory}"
            )

        return documents