from __future__ import annotations

from pathlib import Path
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.rag.database.rag_database_repository import (
    RAGDatabaseRepository,
)
from app.rag.embeddings import RAGEmbeddingService
from app.rag.ingestion import RAGDocumentIngestionService
from app.rag.services.fusion_retrieval_service import FusionRetrievalService


class DBRAGIngestionService:
    """
    Database-backed RAG ingestion pipeline.

    The caller owns the documents row.

    Pipeline:

        File
          ↓
        Loader
          ↓
        Processing
          ↓
        Chunking
          ↓
        Embedding
          ↓
        document_chunks
          ↓
        Retrieval cache invalidation
    """

    def __init__(
        self,
        session: AsyncSession,
        chunk_size: int = 1000,
        chunk_overlap: int = 150,
    ) -> None:
        self.session = session

        self.ingestion_service = RAGDocumentIngestionService(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )

        self.embedding_service = RAGEmbeddingService()

        self.repository = RAGDatabaseRepository(session)

    async def ingest_file(
        self,
        file_path: str | Path,
        document_id: UUID,
        metadata: dict[str, Any] | None = None,
        original_filename: str | None = None,
    ) -> dict[str, Any]:
        """
        Load, chunk, embed, and persist chunks for an
        already-created documents row.

        The caller is responsible for creating the documents
        row and storing file_data.
        """

        path = Path(file_path)

        if not path.exists():
            raise FileNotFoundError(f"Document not found: {path}")

        document_name = (
            original_filename.strip()
            if original_filename and original_filename.strip()
            else path.name
        )

        # -------------------------------------------------
        # Load + process + chunk
        # -------------------------------------------------

        documents = self.ingestion_service.load_file(
            file_path=path,
            metadata=metadata,
        )

        if not documents:
            raise ValueError(f"No chunks generated from {path}.")

        # -------------------------------------------------
        # Preserve the actual uploaded filename
        # -------------------------------------------------

        for document in documents:
            document.metadata["document_name"] = document_name
            document.metadata["original_filename"] = document_name

        # -------------------------------------------------
        # Remove any old chunks for this document.
        #
        # This makes re-ingestion safe and prevents duplicate
        # chunks if an existing document is reprocessed.
        # -------------------------------------------------

        from sqlalchemy import delete

        from app.database.models.knowledge import DocumentChunk

        await self.session.execute(
            delete(DocumentChunk).where(DocumentChunk.document_id == document_id)
        )

        # -------------------------------------------------
        # Create document_chunks rows
        # -------------------------------------------------

        chunks_created = 0

        try:
            for index, document in enumerate(documents):
                content = document.text.strip()

                if not content:
                    continue

                # Generate embedding
                embedding = self.embedding_service.embed_document(content)

                chunk_metadata = {
                    **document.metadata,
                    "document_id": str(document_id),
                    "chunk_index": index,
                    "document_name": document_name,
                    "original_filename": document_name,
                }

                token_count = len(content.split())

                await self.repository.create_chunk(
                    document_id=document_id,
                    chunk_index=index,
                    content=content,
                    token_count=token_count,
                    embedding=embedding,
                    metadata=chunk_metadata,
                )

                chunks_created += 1

            if chunks_created == 0:
                raise ValueError(f"No non-empty chunks generated from {path}.")

            # -------------------------------------------------
            # Commit document chunks
            # -------------------------------------------------

            await self.session.commit()

        except Exception:
            await self.session.rollback()
            raise

        # -------------------------------------------------
        # Invalidate retrieval cache
        # -------------------------------------------------

        try:
            await FusionRetrievalService.invalidate_cache(
                reason="document_upload_or_ingestion"
            )
        except (RuntimeError, ValueError, TypeError, AttributeError):
            # Cache invalidation failure should not make an
            # otherwise successful ingestion fail.
            logger = __import__("logging").getLogger("enterprise_support_ai")
            logger.debug(
                "Retrieval cache invalidation failed during document ingestion",
                exc_info=True,
            )

        return {
            "status": "indexed",
            "document_id": str(document_id),
            "document_name": document_name,
            "document_type": path.suffix.lower(),
            "chunks_created": chunks_created,
            "embedding_dimension": (self.embedding_service.EMBEDDING_DIMENSION),
        }
