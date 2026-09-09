from __future__ import annotations

from pathlib import Path
from typing import Any

from llama_index.core import Document as LlamaIndexDocument

from app.rag.chunking import DocumentChunker
from app.rag.loaders.document_loader import (
    KnowledgeBaseDocumentLoader,
)
from app.rag.processing.document_processing_service import (
    DocumentProcessingService,
)


class RAGDocumentIngestionService:
    """
    Complete RAG ingestion pipeline.

    Pipeline:

        File
          ↓
        Loader
          ↓
        Processing
          ↓
        Chunking
          ↓
        LlamaIndex Document
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

        processed_documents = self.processor.process(loaded_documents)

        chunks = self.chunker.split_documents(processed_documents)

        if not chunks:
            raise ValueError(f"No chunks generated from {file_path}")

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

        loaded_documents = self.loader.load_directory(directory_path)

        processed_documents = self.processor.process(loaded_documents)

        chunks = self.chunker.split_documents(processed_documents)

        if not chunks:
            raise ValueError(f"No chunks generated from {directory_path}")

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
