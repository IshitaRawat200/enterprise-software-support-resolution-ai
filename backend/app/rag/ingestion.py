from __future__ import annotations

from pathlib import Path
from typing import Any
from uuid import UUID

from llama_index.core import Document as LlamaIndexDocument
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.knowledge import DocumentChunk
from app.rag.chunking import DocumentChunker
from app.rag.database.rag_database_repository import (
    RAGDatabaseRepository,
)
from app.rag.embeddings import RAGEmbeddingService
from app.rag.loaders.document_loader import (
    KnowledgeBaseDocumentLoader,
)
from app.rag.processing.document_processing_service import (
    DocumentProcessingService,
)


class RAGDocumentIngestionService:
    """
    Document processing pipeline.

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
    """

    def __init__(
        self,
        chunk_size: int = 1000,
        chunk_overlap: int = 150,
    ) -> None:
        self.loader = KnowledgeBaseDocumentLoader()

        self.processor = DocumentProcessingService()

        self.chunker = DocumentChunker(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )

    def load_file(
        self,
        file_path: str | Path,
        metadata: dict[str, Any] | None = None,
    ) -> list[LlamaIndexDocument]:
        loaded_documents = self.loader.load_file(file_path)

        processed_documents = self.processor.process(
            loaded_documents
        )

        chunks = self.chunker.split_documents(
            processed_documents
        )

        if not chunks:
            raise ValueError(
                f"No chunks generated from {file_path}"
            )

        llama_documents: list[LlamaIndexDocument] = []

        for chunk in chunks:
            chunk_metadata = dict(chunk.metadata)

            if metadata:
                chunk_metadata.update(metadata)

            llama_documents.append(
                LlamaIndexDocument(
                    text=chunk.page_content,
                    metadata=chunk_metadata,
                )
            )

        return llama_documents

    def load_directory(
        self,
        directory_path: str | Path,
        metadata: dict[str, Any] | None = None,
    ) -> list[LlamaIndexDocument]:
        loaded_documents = self.loader.load_directory(
            directory_path
        )

        processed_documents = self.processor.process(
            loaded_documents
        )

        chunks = self.chunker.split_documents(
            processed_documents
        )

        if not chunks:
            raise ValueError(
                f"No chunks generated from {directory_path}"
            )

        llama_documents: list[LlamaIndexDocument] = []

        for chunk in chunks:
            chunk_metadata = dict(chunk.metadata)

            if metadata:
                chunk_metadata.update(metadata)

            llama_documents.append(
                LlamaIndexDocument(
                    text=chunk.page_content,
                    metadata=chunk_metadata,
                )
            )

        return llama_documents


class DBRAGIngestionService:
    """
    Database-backed RAG ingestion service.

    This service connects the document-processing pipeline
    to PostgreSQL.

    Pipeline:

        Uploaded File
             ↓
        RAGDocumentIngestionService
             ↓
        Chunks
             ↓
        Local Embedding Model
             ↓
        document_chunks
             ↓
        Retrieval Cache Invalidation
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

        self.repository = RAGDatabaseRepository(
            session
        )

    async def ingest_file(
        self,
        file_path: str | Path,
        document_id: UUID,
        metadata: dict[str, Any] | None = None,
    ) -> int:
        """
        Load, chunk, embed, and persist one document.

        Returns:
            Number of stored chunks.
        """

        documents = self.ingestion_service.load_file(
            file_path=file_path,
            metadata=metadata,
        )

        if not documents:
            raise ValueError(
                f"No documents generated from {file_path}"
            )

        chunk_rows: list[DocumentChunk] = []

        for chunk_index, document in enumerate(documents):
            content = document.text.strip()

            if not content:
                continue

            embedding = self.embedding_service.embed_document(
                content
            )

            chunk_metadata = dict(
                document.metadata or {}
            )

            chunk_metadata["document_id"] = str(
                document_id
            )

            chunk_metadata["chunk_index"] = (
                chunk_index
            )

            chunk_rows.append(
                DocumentChunk(
                    document_id=document_id,
                    chunk_index=chunk_index,
                    content=content,
                    token_count=None,
                    embedding=embedding,
                    metadata=chunk_metadata,
                )
            )

        if not chunk_rows:
            raise ValueError(
                f"No usable chunks generated from {file_path}"
            )

        self.session.add_all(chunk_rows)

        await self.session.flush()

        return len(chunk_rows)

    async def ingest_directory(
        self,
        directory_path: str | Path,
        document_id: UUID,
        metadata: dict[str, Any] | None = None,
    ) -> int:
        """
        Load, chunk, embed, and persist documents from
        a directory.
        """

        documents = self.ingestion_service.load_directory(
            directory_path=directory_path,
            metadata=metadata,
        )

        if not documents:
            raise ValueError(
                f"No documents generated from {directory_path}"
            )

        chunk_rows: list[DocumentChunk] = []

        for chunk_index, document in enumerate(documents):
            content = document.text.strip()

            if not content:
                continue

            embedding = self.embedding_service.embed_document(
                content
            )

            chunk_metadata = dict(
                document.metadata or {}
            )

            chunk_metadata["document_id"] = str(
                document_id
            )

            chunk_metadata["chunk_index"] = (
                chunk_index
            )

            chunk_rows.append(
                DocumentChunk(
                    document_id=document_id,
                    chunk_index=chunk_index,
                    content=content,
                    token_count=None,
                    embedding=embedding,
                    metadata=chunk_metadata,
                )
            )

        if not chunk_rows:
            raise ValueError(
                f"No usable chunks generated from {directory_path}"
            )

        self.session.add_all(chunk_rows)

        await self.session.flush()

        return len(chunk_rows)