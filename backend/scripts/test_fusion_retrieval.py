from __future__ import annotations

import asyncio
from pathlib import Path

from app.rag.ingestion import (
    RAGDocumentIngestionService,
)
from app.rag.services.fusion_retrieval_service import (
    FusionRetrievalService,
)


async def main() -> None:
    project_root = Path(__file__).resolve().parents[2]

    knowledge_base = (
        project_root
        / "data"
        / "knowledge_base"
    )

    ingestion_service = (
        RAGDocumentIngestionService(
            chunk_size=1000,
            chunk_overlap=150,
        )
    )

    documents = (
        ingestion_service.load_directory(
            knowledge_base
        )
    )

    print(
        f"Loaded {len(documents)} chunks."
    )

    retrieval_service = (
        FusionRetrievalService(
            documents=documents,
            similarity_top_k=5,
        )
    )

    query = (
        "How do I configure SSO?"
    )

    result = await retrieval_service.query(
        query
    )

    print("\nQUERY:")
    print(result["query"])

    print("\nRESULT COUNT:")
    print(result["result_count"])

    print("\nRETRIEVED EVIDENCE:")

    for index, item in enumerate(
        result["results"],
        start=1,
    ):
        print(
            f"\n--- Result {index} ---"
        )

        print(
            f"Title: {item['title']}"
        )

        print(
            f"Score: {item['relevance_score']}"
        )

        print(
            f"Source: {item['source']}"
        )

        print(
            f"Content:\n{item['content']}"
        )


if __name__ == "__main__":
    asyncio.run(main())