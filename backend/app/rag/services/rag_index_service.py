from __future__ import annotations

from pathlib import Path

from llama_index.core import (
    Document,
    Settings,
    StorageContext,
    VectorStoreIndex,
    load_index_from_storage,
)

from app.rag.embeddings import create_embedding_model


class RAGIndexService:
    """
    Manages the persistent LlamaIndex vector index.

    The index is built during ingestion and loaded
    during query time.
    """

    def __init__(
        self,
        index_directory: str | Path,
    ) -> None:

        self.index_directory = Path(index_directory)

        self._configure_embeddings()

    @staticmethod
    def _configure_embeddings() -> None:

        Settings.embed_model = create_embedding_model()

    def build(
        self,
        documents: list[Document],
    ) -> VectorStoreIndex:

        if not documents:
            raise ValueError(
                "At least one document is required to build the RAG index."
            )

        index = VectorStoreIndex.from_documents(documents)

        self.index_directory.mkdir(
            parents=True,
            exist_ok=True,
        )

        index.storage_context.persist(persist_dir=str(self.index_directory))

        return index

    def load(self) -> VectorStoreIndex:

        if not self.index_directory.exists():
            raise FileNotFoundError(
                f"RAG index directory does not exist: {self.index_directory}"
            )

        storage_context = StorageContext.from_defaults(
            persist_dir=str(self.index_directory)
        )

        return load_index_from_storage(storage_context)

    def exists(self) -> bool:
        return self.index_directory.exists()
