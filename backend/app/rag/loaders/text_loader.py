from __future__ import annotations

from pathlib import Path

from langchain_community.document_loaders import TextLoader


class TextDocumentLoader:
    """
    Loads plain-text and Markdown documents.

    Supported:
        .txt
        .md
    """

    SUPPORTED_EXTENSIONS = {
        ".txt",
        ".md",
    }

    def load(self, file_path: str | Path):
        path = Path(file_path)

        if not path.exists():
            raise FileNotFoundError(
                f"Document not found: {path}"
            )

        if not path.is_file():
            raise ValueError(
                f"Path is not a file: {path}"
            )

        if path.suffix.lower() not in self.SUPPORTED_EXTENSIONS:
            raise ValueError(
                f"Unsupported text document type: "
                f"{path.suffix}"
            )

        loader = TextLoader(
            str(path),
            encoding="utf-8",
        )

        return loader.load()