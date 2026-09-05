from __future__ import annotations

import asyncio
from pathlib import Path

from app.agents.retrieval.retrieval_agent import RetrievalAgent
from app.rag.ingestion import RAGDocumentIngestionService


async def main() -> None:

    project_root = Path(__file__).resolve().parents[2]

    knowledge_base = (
        project_root
        / "data"
        / "knowledge_base"
    )

    ingestion_service = RAGDocumentIngestionService()

    documents = ingestion_service.load_directory(
        knowledge_base
    )

    print(
        f"Loaded {len(documents)} chunks."
    )

    agent = RetrievalAgent(
        documents=documents
    )

    query = "How do I configure SSO?"

    result = await agent.retrieve_and_analyze(
        query
    )

    print("\nRETRIEVAL AGENT RESULT:")
    print(
        result.model_dump_json(
            indent=2
        )
    )


if __name__ == "__main__":
    asyncio.run(main())