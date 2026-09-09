from __future__ import annotations

from pathlib import Path
from typing import ClassVar

from langchain_community.document_loaders import (
    UnstructuredHTMLLoader,
)


class HTMLDocumentLoader:
    """
    Loads HTML documents.

    Supported:
        .html
        .htm
    """

    SUPPORTED_EXTENSIONS: ClassVar[set[str]] = {
        ".html",
        ".htm",
    }

    def load(self, file_path: str | Path):
        path = Path(file_path)

        if not path.exists():
            raise FileNotFoundError(f"HTML document not found: {path}")

        if not path.is_file():
            raise ValueError(f"Path is not a file: {path}")

        if path.suffix.lower() not in self.SUPPORTED_EXTENSIONS:
            raise ValueError(f"Unsupported HTML document type: {path.suffix}")

        loader = UnstructuredHTMLLoader(str(path))

        return loader.load()
