from __future__ import annotations

from pathlib import Path

from langchain_community.document_loaders import PyPDFLoader


class PDFDocumentLoader:
    """
    Loads PDF documents.

    Supported:
        .pdf
    """

    SUPPORTED_EXTENSIONS = {
        ".pdf",
    }

    def load(self, file_path: str | Path):
        path = Path(file_path)

        if not path.exists():
            raise FileNotFoundError(
                f"PDF document not found: {path}"
            )

        if not path.is_file():
            raise ValueError(
                f"Path is not a file: {path}"
            )

        if path.suffix.lower() not in self.SUPPORTED_EXTENSIONS:
            raise ValueError(
                f"Unsupported PDF document type: "
                f"{path.suffix}"
            )

        loader = PyPDFLoader(
            str(path)
        )

        return loader.load()