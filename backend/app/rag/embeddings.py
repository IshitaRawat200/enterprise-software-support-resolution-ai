from __future__ import annotations

from sentence_transformers import SentenceTransformer


EMBEDDING_MODEL_NAME = (
    "Orange/orange-nomic-v1.5-1536"
)


class RAGEmbeddingService:
    """
    Generates 1536-dimensional embeddings for RAG.

    The database column is:

        document_chunks.embedding
        -> vector(1536)

    Therefore the same embedding model must be used
    for both document ingestion and customer queries.
    """

    EMBEDDING_DIMENSION = 1536

    def __init__(self) -> None:
        self.model = SentenceTransformer(
            EMBEDDING_MODEL_NAME,
            trust_remote_code=True,
        )

    def embed_document(
        self,
        text: str,
    ) -> list[float]:

        if not text or not text.strip():
            raise ValueError(
                "Document text cannot be empty."
            )

        embedding = self.model.encode(
            f"search_document: {text.strip()}",
            normalize_embeddings=True,
        )

        vector = embedding.tolist()

        if len(vector) != self.EMBEDDING_DIMENSION:
            raise ValueError(
                "Embedding dimension mismatch. "
                f"Expected {self.EMBEDDING_DIMENSION}, "
                f"received {len(vector)}."
            )

        return vector

    def embed_query(
        self,
        query: str,
    ) -> list[float]:

        if not query or not query.strip():
            raise ValueError(
                "Query cannot be empty."
            )

        embedding = self.model.encode(
            f"search_query: {query.strip()}",
            normalize_embeddings=True,
        )

        vector = embedding.tolist()

        if len(vector) != self.EMBEDDING_DIMENSION:
            raise ValueError(
                "Embedding dimension mismatch. "
                f"Expected {self.EMBEDDING_DIMENSION}, "
                f"received {len(vector)}."
            )

        return vector