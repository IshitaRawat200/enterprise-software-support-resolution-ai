from __future__ import annotations

from typing import Any

from llama_index.core import (
    Document,
    Settings,
    VectorStoreIndex,
)
from llama_index.core.embeddings import BaseEmbedding
from llama_index.core.retrievers import (
    QueryFusionRetriever,
)
from llama_index.llms.groq import Groq
from llama_index.retrievers.bm25 import BM25Retriever
from pydantic import PrivateAttr
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.rag.database.rag_database_repository import (
    RAGDatabaseRepository,
)
from app.rag.embeddings import RAGEmbeddingService


class RAGLlamaIndexEmbedding(BaseEmbedding):
    """
    Adapter between the project's local embedding service
    and LlamaIndex.

    Model:

        Orange/orange-nomic-v1.5-1536

    Dimension:

        1536
    """

    _embedding_service: RAGEmbeddingService = PrivateAttr()

    def __init__(self) -> None:

        super().__init__()

        self._embedding_service = RAGEmbeddingService()

    def _get_query_embedding(
        self,
        query: str,
    ) -> list[float]:

        return self._embedding_service.embed_query(query)

    async def _aget_query_embedding(
        self,
        query: str,
    ) -> list[float]:

        return self._get_query_embedding(query)

    def _get_text_embedding(
        self,
        text: str,
    ) -> list[float]:

        return self._embedding_service.embed_document(text)

    def _get_text_embeddings(
        self,
        texts: list[str],
    ) -> list[list[float]]:

        return [self._get_text_embedding(text) for text in texts]


class FusionRetrievalService:
    """
    Hybrid documentation retrieval.

    Architecture:

        Customer Query
              |
        +-----+------+
        |            |
        v            v
      Vector        BM25
      Search        Search
        |            |
        +-----+------+
              |
              v
       QueryFusionRetriever
              |
              v
      Reciprocal Rank Fusion
              |
              v
        Ranked Evidence

    PostgreSQL/Supabase is the knowledge-base
    source of truth.
    """

    def __init__(
        self,
        session: AsyncSession,
        similarity_top_k: int = 5,
        minimum_similarity: float = 0.0,
    ) -> None:

        if similarity_top_k <= 0:
            raise ValueError("similarity_top_k must be greater than zero.")

        if not 0.0 <= minimum_similarity <= 1.0:
            raise ValueError("minimum_similarity must be between 0.0 and 1.0.")

        self.session = session

        self.similarity_top_k = similarity_top_k

        self.minimum_similarity = minimum_similarity

        self.repository = RAGDatabaseRepository(session)

        self.vector_index = None
        self.vector_retriever = None
        self.bm25_retriever = None
        self.fusion_retriever = None

    # ============================================================
    # BUILD INDEX
    # ============================================================

    async def _build_retrieval_index(
        self,
    ) -> None:
        """
        Build:

            Vector Search
                  +
               BM25
                  ↓
                RRF
        """

        chunks = await self.repository.list_chunks()

        if not chunks:
            raise ValueError("No knowledge-base chunks are available for retrieval.")

        documents: list[Document] = []

        for chunk in chunks:
            content = (chunk.get("content") or "").strip()

            if not content:
                continue

            metadata = dict(
                chunk.get(
                    "metadata",
                    {},
                )
            )

            documents.append(
                Document(
                    text=content,
                    metadata=metadata,
                )
            )

        if not documents:
            raise ValueError("No usable knowledge-base documents were found.")

        # --------------------------------------------------------
        # Configure local embedding model
        # --------------------------------------------------------

        Settings.embed_model = RAGLlamaIndexEmbedding()

        # --------------------------------------------------------
        # Vector index
        # --------------------------------------------------------

        self.vector_index = VectorStoreIndex.from_documents(documents)

        self.vector_retriever = self.vector_index.as_retriever(
            similarity_top_k=(self.similarity_top_k)
        )

        # --------------------------------------------------------
        # BM25
        # --------------------------------------------------------

        nodes = list(self.vector_index.docstore.docs.values())

        if not nodes:
            raise ValueError("No nodes were created for BM25 retrieval.")

        self.bm25_retriever = BM25Retriever.from_defaults(
            nodes=nodes,
            similarity_top_k=(
                min(
                    self.similarity_top_k,
                    len(nodes),
                )
            ),
        )

        # --------------------------------------------------------
        # QueryFusionRetriever
        # --------------------------------------------------------

        self.fusion_retriever = QueryFusionRetriever(
            retrievers=[
                self.vector_retriever,
                self.bm25_retriever,
            ],
            llm=self._create_fusion_llm(),
            similarity_top_k=(
                min(
                    self.similarity_top_k,
                    len(nodes),
                )
            ),
            num_queries=1,
            mode="reciprocal_rerank",
            use_async=True,
            verbose=False,
        )

    # ============================================================
    # FUSION LLM
    # ============================================================

    @staticmethod
    def _create_fusion_llm() -> Groq:

        settings = get_settings()

        if not settings.groq_api_key:
            raise RuntimeError("GROQ_API_KEY is not configured.")

        return Groq(
            model=settings.groq_simple_model,
            api_key=settings.groq_api_key,
            temperature=0.0,
        )

    # ============================================================
    # VECTOR SEARCH
    # ============================================================

    async def _retrieve_vector_results(
        self,
        query: str,
    ) -> dict[str, float]:
        """
        Run semantic vector retrieval separately so we
        retain the actual semantic similarity score.

        This score is used for evidence confidence.

        RRF score is NOT used as confidence.
        """

        if self.vector_retriever is None:
            await self._build_retrieval_index()

        if self.vector_retriever is None:
            raise RuntimeError("Vector retriever was not initialized.")

        results = await self.vector_retriever.aretrieve(query)

        scores: dict[str, float] = {}

        for item in results:
            node = item.node

            document_id = node.metadata.get("document_id") if node.metadata else None

            chunk_id = node.metadata.get("chunk_id") if node.metadata else None

            key = (
                str(chunk_id)
                if chunk_id
                else str(document_id)
                if document_id
                else node.get_content()
            )

            score = float(item.score) if item.score is not None else 0.0

            scores[key] = max(
                scores.get(key, 0.0),
                score,
            )

        return scores

    # ============================================================
    # FUSION RETRIEVAL
    # ============================================================

    async def retrieve(
        self,
        query: str,
    ) -> list[Any]:
        """
        Run Vector + BM25 + RRF.
        """

        if not query or not query.strip():
            raise ValueError("Retrieval query cannot be empty.")

        if self.fusion_retriever is None:
            await self._build_retrieval_index()

        if self.fusion_retriever is None:
            raise RuntimeError("Fusion retriever was not initialized.")

        return await self.fusion_retriever.aretrieve(query.strip())

    # ============================================================
    # EVIDENCE
    # ============================================================

    async def retrieve_evidence(
        self,
        query: str,
    ) -> list[dict[str, Any]]:
        """
        Return ranked evidence.

        Each result contains:

            vector_score
            rrf_score
            source
            document metadata
        """

        query = query.strip()

        if not query:
            raise ValueError("Retrieval query cannot be empty.")

        # --------------------------------------------------------
        # Run RRF
        # --------------------------------------------------------

        fusion_results = await self.retrieve(query)

        # --------------------------------------------------------
        # Run vector retrieval separately to obtain
        # meaningful semantic similarity scores.
        # --------------------------------------------------------

        vector_scores = await self._retrieve_vector_results(query)

        evidence: list[dict[str, Any]] = []

        for item in fusion_results:
            node = item.node

            metadata = node.metadata or {}

            # ----------------------------------------------------
            # RRF score
            # ----------------------------------------------------

            rrf_score = float(item.score) if item.score is not None else 0.0

            # ----------------------------------------------------
            # Identify chunk
            # ----------------------------------------------------

            chunk_id = metadata.get("chunk_id")

            document_id = metadata.get("document_id")

            key = (
                str(chunk_id)
                if chunk_id
                else str(document_id)
                if document_id
                else node.get_content()
            )

            # ----------------------------------------------------
            # Semantic/vector score
            # ----------------------------------------------------

            vector_score = vector_scores.get(
                key,
                0.0,
            )

            vector_score = max(
                0.0,
                min(
                    1.0,
                    vector_score,
                ),
            )

            # ----------------------------------------------------
            # Minimum semantic relevance filter
            # ----------------------------------------------------

            if vector_score < self.minimum_similarity:
                continue

            # ----------------------------------------------------
            # Source fallback
            # ----------------------------------------------------

            source = (
                metadata.get("source_url") or metadata.get("document_name") or "unknown"
            )

            title = (
                metadata.get("title")
                or metadata.get("document_name")
                or "Documentation"
            )

            evidence.append(
                {
                    "title": title,
                    "content": node.get_content(),
                    "source": source,
                    # Semantic relevance.
                    "vector_score": round(
                        vector_score,
                        4,
                    ),
                    # Fusion ranking score.
                    "rrf_score": round(
                        rrf_score,
                        4,
                    ),
                    "relevance_score": round(
                        vector_score,
                        4,
                    ),
                    "document_name": metadata.get("document_name"),
                    "document_id": metadata.get("document_id"),
                    "chunk_id": metadata.get("chunk_id"),
                    "chunk_index": metadata.get("chunk_index"),
                    "product_name": metadata.get("product_name"),
                    "product_version": metadata.get("product_version"),
                    "version": metadata.get("version"),
                }
            )

        # --------------------------------------------------------
        # Sort final evidence primarily by semantic relevance,
        # then by RRF score.
        #
        # RRF remains part of the retrieval architecture,
        # while vector similarity provides a meaningful
        # confidence signal.
        # --------------------------------------------------------

        evidence.sort(
            key=lambda item: (
                item["vector_score"],
                item["rrf_score"],
            ),
            reverse=True,
        )

        return evidence

    # ============================================================
    # QUERY
    # ============================================================

    async def query(
        self,
        query: str,
    ) -> dict[str, Any]:

        if not query or not query.strip():
            raise ValueError("Retrieval query cannot be empty.")

        evidence = await self.retrieve_evidence(query)

        return {
            "query": query.strip(),
            "result_count": len(evidence),
            "results": evidence,
        }
