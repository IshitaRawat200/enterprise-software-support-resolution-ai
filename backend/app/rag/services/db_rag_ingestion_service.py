from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.rag.database.rag_database_repository import (
    RAGDatabaseRepository,
)
from app.rag.embeddings import RAGEmbeddingService
from app.rag.ingestion import RAGDocumentIngestionService


class DBRAGIngestionService:
    """
    Database-backed RAG ingestion pipeline.

    Pipeline:

        File
          ↓
        Loader
          ↓
        Processing
          ↓
        Chunking
          ↓
        LlamaIndex Documents
          ↓
        Embedding
          ↓
        documents
          ↓
        document_chunks
          ↓
        Supabase pgvector
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
        metadata: dict[str, Any] | None = None,
        original_filename: str | None = None,
    ) -> dict[str, Any]:

        path = Path(file_path)

        if not path.exists():
            raise FileNotFoundError(
                f"Document not found: {path}"
            )

        # -------------------------------------------------
        # Determine the canonical document name.
        #
        # Swagger uploads are stored temporarily, so
        # path.name may be something like:
        #
        #     tmpuiiusnvc.pdf
        #
        # We want to preserve the actual uploaded filename:
        #
        #     production_incident_response.pdf
        # -------------------------------------------------

        document_name = (
            original_filename.strip()
            if original_filename
            and original_filename.strip()
            else path.name
        )

        # -------------------------------------------------
        # Create deterministic content hash.
        # -------------------------------------------------

        file_bytes = path.read_bytes()

        content_hash = hashlib.sha256(
            file_bytes
        ).hexdigest()

        # -------------------------------------------------
        # Avoid ingesting the same document twice.
        # -------------------------------------------------

        existing_document_id = (
            await self.repository.find_document_by_hash(
                content_hash
            )
        )

        if existing_document_id is not None:

            existing_chunk_count = (
                await self.repository.count_chunks(
                    existing_document_id
                )
            )

            return {
                "status": "already_exists",
                "document_id": str(
                    existing_document_id
                ),
                "document_name": document_name,
                "document_type": path.suffix.lower(),
                "chunks_created": (
                    existing_chunk_count
                ),
                "embedding_dimension": (
                    self.embedding_service.EMBEDDING_DIMENSION
                ),
            }

        # -------------------------------------------------
        # Load + process + chunk.
        # -------------------------------------------------

        documents = self.ingestion_service.load_file(
            file_path=path,
            metadata=metadata,
        )

        if not documents:
            raise ValueError(
                f"No chunks generated from {path}."
            )

        # -------------------------------------------------
        # Replace temporary loader filename metadata with
        # the original uploaded filename.
        # -------------------------------------------------

        for document in documents:

            document.metadata["document_name"] = (
                document_name
            )

            document.metadata["original_filename"] = (
                document_name
            )

        # -------------------------------------------------
        # Extract metadata from the first chunk.
        # -------------------------------------------------

        first_metadata = dict(
            documents[0].metadata
        )

        # -------------------------------------------------
        # Build document-level metadata.
        #
        # Remove temporary/internal fields and make the
        # original uploaded filename canonical.
        # -------------------------------------------------

        document_metadata = {
            key: value
            for key, value in first_metadata.items()
            if key not in {
                "chunk_index",
                "file_path",
                "document_name",
                "original_filename",
            }
        }

        document_metadata["document_name"] = (
            document_name
        )

        document_metadata["original_filename"] = (
            document_name
        )

        # -------------------------------------------------
        # Create documents row.
        # -------------------------------------------------

        document_id = (
            await self.repository.create_document(
                document_name=document_name,
                document_type=path.suffix.lower(),
                source_url=first_metadata.get(
                    "source_url"
                ),
                product_name=first_metadata.get(
                    "product_name"
                ),
                product_version=first_metadata.get(
                    "product_version"
                ),
                version=first_metadata.get(
                    "version"
                ),
                content_hash=content_hash,
                metadata=document_metadata,
            )
        )

        # -------------------------------------------------
        # Create document_chunks rows.
        # -------------------------------------------------

        chunks_created = 0

        try:

            for index, document in enumerate(
                documents
            ):

                content = document.text.strip()

                if not content:
                    continue

                # -------------------------------------------------
                # Generate 1536-dimensional embedding.
                # -------------------------------------------------

                embedding = (
                    self.embedding_service.embed_document(
                        content
                    )
                )

                # -------------------------------------------------
                # Store chunk metadata.
                # -------------------------------------------------

                chunk_metadata = {
                    **document.metadata,
                    "document_id": str(
                        document_id
                    ),
                    "chunk_index": index,
                    "document_name": document_name,
                    "original_filename": document_name,
                }

                token_count = len(
                    content.split()
                )

                # -------------------------------------------------
                # Insert chunk into document_chunks.
                # -------------------------------------------------

                await self.repository.create_chunk(
                    document_id=document_id,
                    chunk_index=index,
                    content=content,
                    token_count=token_count,
                    embedding=embedding,
                    metadata=chunk_metadata,
                )

                chunks_created += 1

            # -------------------------------------------------
            # Commit document + chunks.
            # -------------------------------------------------

            await self.session.commit()

        except Exception:

            await self.session.rollback()

            raise

        # -------------------------------------------------
        # Return ingestion result.
        # -------------------------------------------------

        return {
            "status": "indexed",
            "document_id": str(
                document_id
            ),
            "document_name": document_name,
            "document_type": path.suffix.lower(),
            "chunks_created": chunks_created,
            "embedding_dimension": (
                self.embedding_service.EMBEDDING_DIMENSION
            ),
        }