from __future__ import annotations

import json
from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


class RAGDatabaseRepository:
    """
    Database repository for knowledge-base documents
    and document chunks.

    PostgreSQL/Supabase is the source of truth.
    """

    def __init__(
        self,
        session: AsyncSession,
    ) -> None:

        self.session = session

    # ============================================================
    # DOCUMENT INGESTION
    # ============================================================

    async def find_document_by_hash(
        self,
        content_hash: str,
    ) -> UUID | None:

        result = await self.session.execute(
            text(
                """
                SELECT id
                FROM public.documents
                WHERE content_hash = :content_hash
                LIMIT 1
                """
            ),
            {
                "content_hash": content_hash,
            },
        )

        row = result.first()

        if row is None:
            return None

        return row[0]

    async def create_document(
        self,
        document_name: str,
        document_type: str | None,
        source_url: str | None,
        product_name: str | None,
        product_version: str | None,
        version: str | None,
        content_hash: str | None,
        metadata: dict,
    ) -> UUID:

        document_id = uuid4()

        await self.session.execute(
            text(
                """
                INSERT INTO public.documents (
                    id,
                    knowledge_article_id,
                    document_name,
                    document_type,
                    source_url,
                    product_name,
                    product_version,
                    version,
                    content_hash,
                    metadata,
                    created_at
                )
                VALUES (
                    :id,
                    NULL,
                    :document_name,
                    :document_type,
                    :source_url,
                    :product_name,
                    :product_version,
                    :version,
                    :content_hash,
                    CAST(:metadata AS jsonb),
                    :created_at
                )
                """
            ),
            {
                "id": document_id,
                "document_name": document_name,
                "document_type": document_type,
                "source_url": source_url,
                "product_name": product_name,
                "product_version": product_version,
                "version": version,
                "content_hash": content_hash,
                "metadata": json.dumps(
                    metadata,
                    ensure_ascii=False,
                ),
                "created_at": datetime.now(UTC),
            },
        )

        return document_id

    async def create_chunk(
        self,
        document_id: UUID,
        chunk_index: int,
        content: str,
        token_count: int | None,
        embedding: list[float],
        metadata: dict,
    ) -> UUID:

        chunk_id = uuid4()

        embedding_text = "[" + ",".join(str(value) for value in embedding) + "]"

        await self.session.execute(
            text(
                """
                INSERT INTO public.document_chunks (
                    id,
                    document_id,
                    chunk_index,
                    content,
                    token_count,
                    embedding,
                    metadata,
                    created_at
                )
                VALUES (
                    :id,
                    :document_id,
                    :chunk_index,
                    :content,
                    :token_count,
                    CAST(:embedding AS vector),
                    CAST(:metadata AS jsonb),
                    :created_at
                )
                """
            ),
            {
                "id": chunk_id,
                "document_id": document_id,
                "chunk_index": chunk_index,
                "content": content,
                "token_count": token_count,
                "embedding": embedding_text,
                "metadata": json.dumps(
                    metadata,
                    ensure_ascii=False,
                ),
                "created_at": datetime.now(UTC),
            },
        )

        return chunk_id

    async def count_chunks(
        self,
        document_id: UUID,
    ) -> int:

        result = await self.session.execute(
            text(
                """
                SELECT COUNT(*)
                FROM public.document_chunks
                WHERE document_id = :document_id
                """
            ),
            {
                "document_id": document_id,
            },
        )

        return int(result.scalar_one())

    # ============================================================
    # RETRIEVAL
    # ============================================================

    async def list_chunks(
        self,
        limit: int = 10000,
    ) -> list[dict]:

        if limit <= 0:
            raise ValueError("limit must be greater than zero.")

        result = await self.session.execute(
            text(
                """
                SELECT
                    dc.id,
                    dc.document_id,
                    dc.chunk_index,
                    dc.content,
                    dc.token_count,
                    dc.metadata,
                    d.document_name,
                    d.document_type,
                    d.source_url,
                    d.product_name,
                    d.product_version,
                    d.version
                FROM public.document_chunks AS dc
                JOIN public.documents AS d
                    ON d.id = dc.document_id
                ORDER BY
                    dc.document_id,
                    dc.chunk_index
                LIMIT :limit
                """
            ),
            {
                "limit": limit,
            },
        )

        rows = result.mappings().all()

        chunks: list[dict] = []

        for row in rows:
            metadata = row["metadata"] or {}

            if isinstance(metadata, str):
                metadata = json.loads(metadata)

            combined_metadata = {
                **metadata,
                "document_id": str(row["document_id"]),
                "chunk_id": str(row["id"]),
                "chunk_index": row["chunk_index"],
                "document_name": row["document_name"],
                "document_type": row["document_type"],
                "source_url": row["source_url"],
                "product_name": row["product_name"],
                "product_version": row["product_version"],
                "version": row["version"],
            }

            chunks.append(
                {
                    "id": row["id"],
                    "document_id": row["document_id"],
                    "chunk_index": row["chunk_index"],
                    "content": row["content"],
                    "token_count": row["token_count"],
                    "metadata": combined_metadata,
                }
            )

        return chunks
