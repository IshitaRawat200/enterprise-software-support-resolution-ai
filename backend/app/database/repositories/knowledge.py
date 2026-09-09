from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.knowledge import (
    Document,
    DocumentChunk,
    KnowledgeArticle,
    KnowledgeArticleUsage,
)


class KnowledgeRepository:
    """Database operations for knowledge and RAG data."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_article_by_id(
        self,
        article_id: UUID,
    ) -> KnowledgeArticle | None:
        result = await self.session.execute(
            select(KnowledgeArticle).where(KnowledgeArticle.id == article_id)
        )
        return result.scalar_one_or_none()

    async def get_article_by_code(
        self,
        article_code: str,
    ) -> KnowledgeArticle | None:
        result = await self.session.execute(
            select(KnowledgeArticle).where(
                KnowledgeArticle.article_code == article_code
            )
        )
        return result.scalar_one_or_none()

    async def get_active_articles(self) -> list[KnowledgeArticle]:
        result = await self.session.execute(
            select(KnowledgeArticle)
            .where(KnowledgeArticle.is_active.is_(True))
            .order_by(KnowledgeArticle.updated_at.desc())
        )
        return list(result.scalars().all())

    async def get_documents_by_article(
        self,
        article_id: UUID,
    ) -> list[Document]:
        result = await self.session.execute(
            select(Document)
            .where(Document.knowledge_article_id == article_id)
            .order_by(Document.created_at.desc())
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

    async def add_article_usage(
        self,
        usage: KnowledgeArticleUsage,
    ) -> KnowledgeArticleUsage:
        self.session.add(usage)
        await self.session.flush()
        await self.session.refresh(usage)
        return usage
