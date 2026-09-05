from __future__ import annotations

from time import perf_counter

from sentence_transformers import SentenceTransformer

from app.observability.logging import logger

EMBEDDING_MODEL_NAME = (
    "Orange/orange-nomic-v1.5-1536"
)


# ============================================================
# SHARED MODEL
# ============================================================

_model: SentenceTransformer | None = None


def get_embedding_model() -> SentenceTransformer:
    """
    Return the shared SentenceTransformer model.

    The model is loaded only once per application process.
    Subsequent calls reuse the same in-memory model.
    """

    global _model

    if _model is not None:
        return _model

    start = perf_counter()

    logger.info(
        "RAG EMBEDDINGS: loading model '%s'",
        EMBEDDING_MODEL_NAME,
    )

    _model = SentenceTransformer(
        EMBEDDING_MODEL_NAME,
        trust_remote_code=True,
    )

    duration = perf_counter() - start

    logger.info(
        "RAG EMBEDDINGS: model loaded in %.3fs",
        duration,
    )

    return _model


# ============================================================
# EMBEDDING SERVICE
# ============================================================

class RAGEmbeddingService:
    """
    Generates 1536-dimensional embeddings for RAG.

    The database column is:

        document_chunks.embedding
        -> vector(1536)

    Therefore the same embedding model must be used
    for both document ingestion and customer queries.

    The underlying SentenceTransformer model is shared
    across service instances.
    """

    EMBEDDING_DIMENSION = 1536

    def __init__(self) -> None:
        """
        Do not load the model here.

        Loading is deferred until the first embedding request.
        """

        self.model = get_embedding_model()

    # ========================================================
    # DOCUMENT EMBEDDING
    # ========================================================

    def embed_document(
        self,
        text: str,
    ) -> list[float]:
        """
        Generate an embedding for a document.
        """

        if not text or not text.strip():
            raise ValueError(
                "Document text cannot be empty."
            )

        start = perf_counter()

        embedding = self.model.encode(
            f"search_document: {text.strip()}",
            normalize_embeddings=True,
        )

        duration = perf_counter() - start

        logger.debug(
            "RAG EMBEDDINGS: document embedding generated "
            "in %.3fs",
            duration,
        )

        vector = embedding.tolist()

        if len(vector) != self.EMBEDDING_DIMENSION:
            raise ValueError(
                "Embedding dimension mismatch. "
                f"Expected {self.EMBEDDING_DIMENSION}, "
                f"received {len(vector)}."
            )

        return vector

    # ========================================================
    # QUERY EMBEDDING
    # ========================================================

    def embed_query(
        self,
        query: str,
    ) -> list[float]:
        """
        Generate an embedding for a customer query.
        """

        if not query or not query.strip():
            raise ValueError(
                "Query cannot be empty."
            )

        start = perf_counter()

        embedding = self.model.encode(
            f"search_query: {query.strip()}",
            normalize_embeddings=True,
        )

        duration = perf_counter() - start

        logger.debug(
            "RAG EMBEDDINGS: query embedding generated "
            "in %.3fs",
            duration,
        )

        vector = embedding.tolist()

        if len(vector) != self.EMBEDDING_DIMENSION:
            raise ValueError(
                "Embedding dimension mismatch. "
                f"Expected {self.EMBEDDING_DIMENSION}, "
                f"received {len(vector)}."
            )

        return vector