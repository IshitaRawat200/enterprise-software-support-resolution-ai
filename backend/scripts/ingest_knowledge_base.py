from __future__ import annotations

import asyncio
from pathlib import Path

from app.database.connection import (
    get_db_session,
)
from app.rag.services.db_rag_ingestion_service import (
    DBRAGIngestionService,
)


async def ingest() -> None:

    project_root = (
        Path(__file__).resolve().parents[2]
    )

    knowledge_base = (
        project_root
        / "data"
        / "knowledge_base"
    )

    print(
        f"Knowledge base: {knowledge_base}"
    )

    if not knowledge_base.exists():
        raise FileNotFoundError(
            f"Knowledge base not found: "
            f"{knowledge_base}"
        )

    async for session in get_db_session():

        service = DBRAGIngestionService(
            session=session
        )

        supported_files = [
            file_path
            for file_path in sorted(
                knowledge_base.iterdir()
            )
            if file_path.is_file()
            and file_path.suffix.lower()
            in {
                ".txt",
                ".md",
                ".pdf",
                ".html",
                ".htm",
            }
        ]

        if not supported_files:
            raise ValueError(
                "No supported documents found."
            )

        print(
            f"Found {len(supported_files)} document(s)."
        )

        for file_path in supported_files:

            print(
                f"\nIngesting: {file_path.name}"
            )

            result = await service.ingest_file(
                file_path
            )

            print(
                f"Status: {result['status']}"
            )

            print(
                f"Document ID: "
                f"{result['document_id']}"
            )

            print(
                f"Chunks: "
                f"{result['chunks_created']}"
            )


def main() -> None:
    asyncio.run(ingest())


if __name__ == "__main__":
    main()