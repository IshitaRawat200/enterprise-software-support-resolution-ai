from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.knowledge import (
    Document,
    DocumentChunk,
    KnowledgeArticleUsage,
)


class KnowledgeRepository:
    """Database operations for RAG data and NIIT article registry rows."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_documents(self) -> list[Document]:
        result = await self.session.execute(
            select(Document).order_by(Document.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_chunks_by_document(
        self,
        document_id: UUID,
    ) -> list[DocumentChunk]:
        result = await self.session.execute(
            select(DocumentChunk)
            .where(DocumentChunk.document_id == document_id)
            .order_by(DocumentChunk.chunk_index.asc())
        )
        return list(result.scalars().all())

    async def add_niit_article_registry_entry(
        self,
        entry: KnowledgeArticleUsage,
    ) -> KnowledgeArticleUsage:
        self.session.add(entry)
        await self.session.flush()
        await self.session.refresh(entry)
        return entry
