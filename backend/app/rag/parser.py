from __future__ import annotations

from pathlib import Path


class DocumentParser:
    """
    Parses supported documentation files into plain text.
    """

    SUPPORTED_EXTENSIONS = {
        ".txt",
        ".md",
    }

    def parse(
        self,
        file_path: str | Path,
    ) -> str:
        path = Path(file_path)

        if not path.exists():
            raise FileNotFoundError(
                f"Document not found: {path}"
            )

        if not path.is_file():
            raise ValueError(
                f"Path is not a file: {path}"
            )

        extension = path.suffix.lower()

        if extension not in self.SUPPORTED_EXTENSIONS:
            raise ValueError(
                f"Unsupported document type: {extension}. "
                f"Supported types: {sorted(self.SUPPORTED_EXTENSIONS)}"
            )

        content = path.read_text(
            encoding="utf-8"
        ).strip()

        if not content:
            raise ValueError(
                f"Document is empty: {path}"
            )

        return content