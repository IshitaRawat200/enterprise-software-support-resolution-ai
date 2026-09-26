from __future__ import annotations

import asyncio
import logging
import os
import re
from typing import Any

from openai import AsyncOpenAI
from ragas.embeddings import embedding_factory
from ragas.llms import llm_factory
from ragas.metrics.collections import (
    AnswerRelevancy,
    ContextPrecision,
    ContextRecall,
    Faithfulness,
)

logger = logging.getLogger("enterprise_support_ai")


TOKEN_PATTERN = re.compile(r"[a-z0-9]+")


class RagasEvaluator:
    """
    Production RAGAS evaluator for ERIS.

    Metrics:

    1. Faithfulness
    2. Answer Relevancy
    3. Context Precision
    4. Context Recall

    Faithfulness and Answer Relevancy do not require
    a trusted reference answer.

    Context Precision and Context Recall require
    a trusted reference answer.

    Evaluation runs asynchronously so it never blocks
    the customer chat response.
    """

    # ================================================================
    # CONFIGURATION
    # ================================================================

    # RAGAS evaluator outputs are short structured results.
    # 1024 tokens is more than enough and reduces unnecessary
    # generation latency.
    EVALUATION_MAX_TOKENS = 1024

    # Safety timeout for an individual RAGAS metric.
    #
    # If OpenRouter/Gemini becomes extremely slow, we do not
    # want one evaluation task to remain pending indefinitely.
    DEFAULT_METRIC_TIMEOUT_SECONDS = 20

    # ================================================================
    # INITIALIZATION
    # ================================================================

    def __init__(self) -> None:
        self.openrouter_api_key = os.getenv("OPENROUTER_API_KEY")

        self.openrouter_base_url = os.getenv(
            "OPENROUTER_BASE_URL",
            "https://openrouter.ai/api/v1",
        )

        self.evaluation_model = os.getenv(
            "RAGAS_EVALUATION_MODEL",
            "google/gemini-2.5-flash",
        )

        self.evaluation_embedding_model = os.getenv(
            "RAGAS_EMBEDDING_MODEL",
            "google/gemini-embedding-001",
        )

        timeout_value = os.getenv(
            "RAGAS_METRIC_TIMEOUT_SECONDS",
            str(self.DEFAULT_METRIC_TIMEOUT_SECONDS),
        )

        try:
            parsed_timeout = int(timeout_value)
        except (TypeError, ValueError):
            parsed_timeout = self.DEFAULT_METRIC_TIMEOUT_SECONDS

        self.metric_timeout_seconds = max(5, parsed_timeout)

        if not self.openrouter_api_key:
            raise RuntimeError("OPENROUTER_API_KEY is not configured.")

        logger.info(
            "RAGAS configuration: "
            "model=%s embedding_model=%s base_url=%s metric_timeout=%ss",
            self.evaluation_model,
            self.evaluation_embedding_model,
            self.openrouter_base_url,
            self.metric_timeout_seconds,
        )

        self._init_lock = asyncio.Lock()
        self._initialized = False

        self.async_client: AsyncOpenAI | None = None
        self.evaluator_llm: Any | None = None
        self.evaluator_embeddings: Any | None = None
        self.faithfulness: Faithfulness | None = None
        self.answer_relevancy: AnswerRelevancy | None = None
        self.context_precision: ContextPrecision | None = None
        self.context_recall: ContextRecall | None = None

    async def ensure_initialized(self) -> None:
        if self._initialized:
            return

        async with self._init_lock:
            if self._initialized:
                return

            logger.info("RAGAS: creating OpenRouter-compatible async client")

            self.async_client = AsyncOpenAI(
                api_key=self.openrouter_api_key,
                base_url=self.openrouter_base_url,
                default_headers=self._build_headers(),
            )

            logger.info("RAGAS: OpenRouter-compatible async client created")

            logger.info(
                "RAGAS: creating evaluator LLM model=%s",
                self.evaluation_model,
            )

            llm_task = asyncio.to_thread(
                llm_factory,
                self.evaluation_model,
                provider="openai",
                client=self.async_client,
                max_tokens=self.EVALUATION_MAX_TOKENS,
            )

            logger.info(
                "RAGAS: creating embeddings model=%s",
                self.evaluation_embedding_model,
            )

            embeddings_task = asyncio.to_thread(
                embedding_factory,
                "openai",
                model=self.evaluation_embedding_model,
                client=self.async_client,
            )

            (
                self.evaluator_llm,
                self.evaluator_embeddings,
            ) = await asyncio.gather(
                llm_task,
                embeddings_task,
            )

            logger.info("RAGAS: evaluator LLM created")

            logger.info("RAGAS: embeddings created")

            logger.info("RAGAS: creating Faithfulness metric")

            self.faithfulness = Faithfulness(
                llm=self.evaluator_llm,
            )

            logger.info("RAGAS: creating AnswerRelevancy metric")

            self.answer_relevancy = AnswerRelevancy(
                llm=self.evaluator_llm,
                embeddings=self.evaluator_embeddings,
            )

            logger.info("RAGAS: creating ContextPrecision metric")

            self.context_precision = ContextPrecision(
                llm=self.evaluator_llm,
            )

            logger.info("RAGAS: creating ContextRecall metric")

            self.context_recall = ContextRecall(
                llm=self.evaluator_llm,
            )

            logger.info("RAGAS: all metrics created")

            self._initialized = True

    async def prewarm(self) -> None:
        await self.ensure_initialized()

    # ================================================================
    # OPENROUTER HEADERS
    # ================================================================

    @staticmethod
    def _build_headers() -> dict[str, str]:
        headers: dict[str, str] = {}

        http_referer = os.getenv("OPENROUTER_HTTP_REFERER")

        title = os.getenv("OPENROUTER_X_TITLE")

        if http_referer:
            headers["HTTP-Referer"] = http_referer

        if title:
            headers["X-Title"] = title

        return headers

    # ================================================================
    # SAFE FLOAT
    # ================================================================

    @staticmethod
    def _safe_float(
        value: Any,
    ) -> float | None:
        if value is None:
            return None

        if isinstance(
            value,
            bool,
        ):
            return None

        try:
            return float(value)

        except (
            TypeError,
            ValueError,
        ):
            return None

    # ================================================================
    # SCORE EXTRACTION
    # ================================================================

    @classmethod
    def _extract_score(
        cls,
        result: Any,
    ) -> float | None:
        """
        Normalize different RAGAS result formats into float.
        """

        if result is None:
            return None

        if isinstance(
            result,
            (int, float),
        ):
            return float(result)

        if isinstance(
            result,
            dict,
        ):
            for key in (
                "score",
                "value",
                "result",
            ):
                if key in result:
                    score = cls._safe_float(result[key])

                    if score is not None:
                        return score

        for attribute in (
            "score",
            "value",
            "result",
        ):
            if hasattr(
                result,
                attribute,
            ):
                try:
                    value = getattr(
                        result,
                        attribute,
                    )

                    score = cls._safe_float(value)

                    if score is not None:
                        return score

                except (AttributeError, TypeError, ValueError):
                    continue

        return cls._safe_float(result)

    # ================================================================
    # RETRIEVAL CONTEXT EXTRACTION
    # ================================================================

    @classmethod
    def _extract_context_from_item(
        cls,
        item: Any,
    ) -> str | None:
        """
        Extract text from ERIS retrieval result objects.
        """

        if item is None:
            return None

        # ------------------------------------------------------------
        # String
        # ------------------------------------------------------------

        if isinstance(
            item,
            str,
        ):
            value = item.strip()

            return value or None

        # ------------------------------------------------------------
        # Bytes
        # ------------------------------------------------------------

        if isinstance(
            item,
            bytes,
        ):
            value = item.decode(errors="replace").strip()

            return value or None

        # ------------------------------------------------------------
        # Dictionary
        # ------------------------------------------------------------

        if isinstance(
            item,
            dict,
        ):
            for key in (
                "content",
                "text",
                "chunk_content",
                "document_content",
                "node_content",
            ):
                value = item.get(key)

                if value:
                    return str(value).strip()

            node = item.get("node")

            if isinstance(
                node,
                dict,
            ):
                for key in (
                    "content",
                    "text",
                    "chunk_content",
                    "document_content",
                    "node_content",
                ):
                    value = node.get(key)

                    if value:
                        return str(value).strip()

            return None

        # ------------------------------------------------------------
        # Object attributes
        # ------------------------------------------------------------

        for attribute in (
            "text",
            "content",
            "chunk_content",
            "document_content",
        ):
            if hasattr(
                item,
                attribute,
            ):
                try:
                    value = getattr(
                        item,
                        attribute,
                    )

                    if value:
                        return str(value).strip()

                except (AttributeError, TypeError, ValueError):
                    continue

        # ------------------------------------------------------------
        # LlamaIndex node
        # ------------------------------------------------------------

        if hasattr(
            item,
            "get_content",
        ):
            try:
                value = item.get_content()

                if value:
                    return str(value).strip()

            except (AttributeError, TypeError, ValueError):
                pass

        return None

    # ================================================================
    # RETRIEVAL CONTEXT LIST
    # ================================================================

    @classmethod
    def _extract_retrieved_contexts(
        cls,
        retrieval_results: Any,
    ) -> list[str]:
        """
        Convert ERIS retrieval output into list[str].
        """

        if not retrieval_results:
            return []

        # ------------------------------------------------------------
        # Wrapper dictionaries
        # ------------------------------------------------------------

        if isinstance(
            retrieval_results,
            dict,
        ):
            for key in (
                "results",
                "retrieval_results",
                "contexts",
                "documents",
            ):
                if key in retrieval_results:
                    retrieval_results = retrieval_results[key]
                    break

        # ------------------------------------------------------------
        # Single string
        # ------------------------------------------------------------

        if isinstance(
            retrieval_results,
            str,
        ):
            context = cls._extract_context_from_item(retrieval_results)

            return [context] if context else []

        # ------------------------------------------------------------
        # Single bytes
        # ------------------------------------------------------------

        if isinstance(
            retrieval_results,
            bytes,
        ):
            context = cls._extract_context_from_item(retrieval_results)

            return [context] if context else []

        # ------------------------------------------------------------
        # Normalize single object
        # ------------------------------------------------------------

        if not isinstance(
            retrieval_results,
            (list, tuple),
        ):
            retrieval_results = [retrieval_results]

        # ------------------------------------------------------------
        # Extract contexts
        # ------------------------------------------------------------

        contexts: list[str] = []

        for item in retrieval_results:
            context = cls._extract_context_from_item(item)

            if context:
                contexts.append(context)

        return contexts

    # ================================================================
    # METRIC TIMEOUT HELPER
    # ================================================================

    async def _run_with_timeout(
        self,
        *,
        metric_name: str,
        request_id: str,
        coroutine: Any,
    ) -> float | None:
        """
        Run one RAGAS metric with a bounded timeout.

        A slow evaluator must not remain pending forever.
        """

        task = asyncio.create_task(coroutine)

        try:
            done, pending = await asyncio.wait(
                {task},
                timeout=self.metric_timeout_seconds,
                return_when=asyncio.FIRST_COMPLETED,
            )

            if task in done:
                return await task

            if task in pending:
                task.cancel()

            logger.error(
                "RAGAS metric timeout request_id=%s metric=%s timeout=%ss",
                request_id,
                metric_name,
                self.metric_timeout_seconds,
            )

            return None

        except (RuntimeError, TypeError, ValueError, AttributeError):
            logger.exception(
                "RAGAS metric wrapper failed request_id=%s metric=%s",
                request_id,
                metric_name,
            )

            return None

    @staticmethod
    def _tokenize(text: str) -> set[str]:
        return {
            token
            for token in TOKEN_PATTERN.findall((text or "").lower())
            if len(token) > 2
        }

    @classmethod
    def _overlap_ratio(
        cls,
        source_text: str,
        target_text: str,
    ) -> float | None:
        source_tokens = cls._tokenize(source_text)
        target_tokens = cls._tokenize(target_text)

        if not source_tokens or not target_tokens:
            return None

        overlap = source_tokens.intersection(target_tokens)

        if not overlap:
            return 0.0

        ratio = len(overlap) / float(len(source_tokens))
        return max(0.0, min(1.0, ratio))

    @classmethod
    def _fallback_scores(
        cls,
        *,
        question: str,
        answer: str,
        retrieved_contexts: list[str],
        reference: str | None,
    ) -> dict[str, float | None]:
        context_blob = "\n".join(retrieved_contexts[:8])

        answer_relevance = cls._overlap_ratio(question, answer)
        context_precision = cls._overlap_ratio(answer, context_blob)

        # Faithfulness fallback tracks how much of the answer appears
        # in retrieved context. This is approximate but deterministic.
        faithfulness = context_precision

        context_recall: float | None = None
        if reference:
            context_recall = cls._overlap_ratio(reference, context_blob)

        return {
            "faithfulness": faithfulness,
            "answer_relevance": answer_relevance,
            "context_precision": context_precision,
            "context_recall": context_recall,
        }

    # ================================================================
    # FAITHFULNESS
    # ================================================================

    async def _evaluate_faithfulness(
        self,
        *,
        request_id: str,
        question: str,
        answer: str,
        retrieved_contexts: list[str],
    ) -> float | None:
        logger.info(
            "RAGAS metric starting request_id=%s metric=faithfulness contexts=%d",
            request_id,
            len(retrieved_contexts),
        )

        try:
            result = await self.faithfulness.ascore(
                user_input=question,
                response=answer,
                retrieved_contexts=retrieved_contexts,
            )

            score = self._extract_score(result)

            logger.info(
                "RAGAS metric completed request_id=%s metric=faithfulness score=%s",
                request_id,
                score,
            )

            return score

        except (RuntimeError, TypeError, ValueError, AttributeError):
            logger.exception(
                "RAGAS metric failed request_id=%s metric=faithfulness",
                request_id,
            )

            return None

    # ================================================================
    # ANSWER RELEVANCY
    # ================================================================

    async def _evaluate_answer_relevance(
        self,
        *,
        request_id: str,
        question: str,
        answer: str,
    ) -> float | None:
        logger.info(
            "RAGAS metric starting request_id=%s metric=answer_relevance",
            request_id,
        )

        try:
            result = await self.answer_relevancy.ascore(
                user_input=question,
                response=answer,
            )

            score = self._extract_score(result)

            logger.info(
                "RAGAS metric completed request_id=%s metric=answer_relevance score=%s",
                request_id,
                score,
            )

            return score

        except (RuntimeError, TypeError, ValueError, AttributeError):
            logger.exception(
                "RAGAS metric failed request_id=%s metric=answer_relevance",
                request_id,
            )

            return None

    # ================================================================
    # CONTEXT PRECISION
    # ================================================================

    async def _evaluate_context_precision(
        self,
        *,
        request_id: str,
        question: str,
        answer: str,
        retrieved_contexts: list[str],
        reference: str | None,
    ) -> float | None:
        if not reference:
            logger.info(
                "RAGAS metric skipped "
                "request_id=%s metric=context_precision "
                "reason=no_trusted_reference",
                request_id,
            )

            return None

        logger.info(
            "RAGAS metric starting request_id=%s metric=context_precision contexts=%d",
            request_id,
            len(retrieved_contexts),
        )

        try:
            result = await self.context_precision.ascore(
                user_input=question,
                retrieved_contexts=retrieved_contexts,
                reference=reference,
            )

            score = self._extract_score(result)

            logger.info(
                "RAGAS metric completed "
                "request_id=%s metric=context_precision score=%s",
                request_id,
                score,
            )

            return score

        except (RuntimeError, TypeError, ValueError, AttributeError):
            logger.exception(
                "RAGAS metric failed request_id=%s metric=context_precision",
                request_id,
            )

            return None

    # ================================================================
    # CONTEXT RECALL
    # ================================================================

    async def _evaluate_context_recall(
        self,
        *,
        request_id: str,
        question: str,
        answer: str,
        retrieved_contexts: list[str],
        reference: str | None,
    ) -> float | None:
        if not reference:
            logger.info(
                "RAGAS metric skipped "
                "request_id=%s metric=context_recall "
                "reason=no_trusted_reference",
                request_id,
            )

            return None

        logger.info(
            "RAGAS metric starting request_id=%s metric=context_recall contexts=%d",
            request_id,
            len(retrieved_contexts),
        )

        try:
            result = await self.context_recall.ascore(
                user_input=question,
                retrieved_contexts=retrieved_contexts,
                reference=reference,
            )

            score = self._extract_score(result)

            logger.info(
                "RAGAS metric completed request_id=%s metric=context_recall score=%s",
                request_id,
                score,
            )

            return score

        except (RuntimeError, TypeError, ValueError, AttributeError):
            logger.exception(
                "RAGAS metric failed request_id=%s metric=context_recall",
                request_id,
            )

            return None

    # ================================================================
    # EVALUATE CASE
    # ================================================================

    async def evaluate_case(
        self,
        *,
        question: str,
        answer: str,
        retrieved_contexts: list[str],
        reference: str | None = None,
        request_id: str = "unknown",
    ) -> dict[str, Any]:
        """
        Evaluate one completed RAG response.

        Independent RAGAS metrics are executed concurrently.
        """

        logger.info(
            "RAGAS case evaluation starting "
            "request_id=%s contexts=%d reference_present=%s",
            request_id,
            len(retrieved_contexts),
            bool(reference),
        )

        await self.ensure_initialized()

        errors: list[str] = []

        question = (question or "").strip()

        answer = (answer or "").strip()

        retrieved_contexts = [
            str(context).strip()
            for context in retrieved_contexts
            if context and str(context).strip()
        ]

        # ------------------------------------------------------------
        # Validate
        # ------------------------------------------------------------

        if not question:
            errors.append("question is empty")

        if not answer:
            errors.append("answer is empty")

        if not retrieved_contexts:
            errors.append("retrieved_contexts is empty")

        if errors:
            logger.warning(
                "RAGAS case evaluation skipped request_id=%s errors=%s",
                request_id,
                errors,
            )

            return {
                "faithfulness": None,
                "answer_relevance": None,
                "context_precision": None,
                "context_recall": None,
                "ragas_evaluated": False,
                "ragas_errors": errors,
            }

        # ------------------------------------------------------------
        # ALL INDEPENDENT METRICS CONCURRENTLY
        # ------------------------------------------------------------

        logger.info(
            "RAGAS concurrent evaluation starting request_id=%s",
            request_id,
        )

        faithfulness_task = self._run_with_timeout(
            metric_name="faithfulness",
            request_id=request_id,
            coroutine=self._evaluate_faithfulness(
                request_id=request_id,
                question=question,
                answer=answer,
                retrieved_contexts=retrieved_contexts,
            ),
        )

        answer_relevance_task = self._run_with_timeout(
            metric_name="answer_relevance",
            request_id=request_id,
            coroutine=self._evaluate_answer_relevance(
                request_id=request_id,
                question=question,
                answer=answer,
            ),
        )

        context_precision_task = self._run_with_timeout(
            metric_name="context_precision",
            request_id=request_id,
            coroutine=self._evaluate_context_precision(
                request_id=request_id,
                question=question,
                answer=answer,
                retrieved_contexts=retrieved_contexts,
                reference=reference,
            ),
        )

        context_recall_task = self._run_with_timeout(
            metric_name="context_recall",
            request_id=request_id,
            coroutine=self._evaluate_context_recall(
                request_id=request_id,
                question=question,
                answer=answer,
                retrieved_contexts=retrieved_contexts,
                reference=reference,
            ),
        )

        (
            faithfulness,
            answer_relevance,
            context_precision,
            context_recall,
        ) = await asyncio.gather(
            faithfulness_task,
            answer_relevance_task,
            context_precision_task,
            context_recall_task,
        )

        logger.info(
            "RAGAS concurrent evaluation finished "
            "request_id=%s "
            "faithfulness=%s "
            "answer_relevance=%s "
            "context_precision=%s "
            "context_recall=%s",
            request_id,
            faithfulness,
            answer_relevance,
            context_precision,
            context_recall,
        )

        # ------------------------------------------------------------
        # COLLECT ERRORS
        # ------------------------------------------------------------

        if faithfulness is None:
            errors.append("faithfulness evaluation returned no score")

        if answer_relevance is None:
            errors.append("answer_relevance evaluation returned no score")

        if reference:
            if context_precision is None:
                errors.append("context_precision evaluation returned no score")

            if context_recall is None:
                errors.append("context_recall evaluation returned no score")

        fallback_scores = self._fallback_scores(
            question=question,
            answer=answer,
            retrieved_contexts=retrieved_contexts,
            reference=reference,
        )

        fallback_used: list[str] = []

        if faithfulness is None and fallback_scores["faithfulness"] is not None:
            faithfulness = fallback_scores["faithfulness"]
            fallback_used.append("faithfulness")

        if answer_relevance is None and fallback_scores["answer_relevance"] is not None:
            answer_relevance = fallback_scores["answer_relevance"]
            fallback_used.append("answer_relevance")

        if (
            context_precision is None
            and fallback_scores["context_precision"] is not None
        ):
            context_precision = fallback_scores["context_precision"]
            fallback_used.append("context_precision")

        if context_recall is None and fallback_scores["context_recall"] is not None:
            context_recall = fallback_scores["context_recall"]
            fallback_used.append("context_recall")

        if fallback_used:
            errors.append("fallback scores used for: " + ", ".join(fallback_used))

        # ------------------------------------------------------------
        # EVALUATION STATUS
        # ------------------------------------------------------------

        ragas_evaluated = any(
            score is not None
            for score in (
                faithfulness,
                answer_relevance,
                context_precision,
                context_recall,
            )
        )

        if (
            faithfulness is not None
            and answer_relevance is not None
            and (
                not reference
                or (context_precision is not None and context_recall is not None)
            )
        ):
            evaluation_status = "completed"

        elif ragas_evaluated:
            evaluation_status = "partial"

        else:
            evaluation_status = "failed"

        result: dict[str, Any] = {
            "faithfulness": faithfulness,
            "answer_relevance": answer_relevance,
            "context_precision": context_precision,
            "context_recall": context_recall,
            "ragas_evaluated": ragas_evaluated,
            "evaluation_status": evaluation_status,
            "ragas_errors": errors,
        }

        logger.info(
            "RAGAS case evaluation completed "
            "request_id=%s "
            "faithfulness=%s "
            "answer_relevance=%s "
            "context_precision=%s "
            "context_recall=%s "
            "ragas_evaluated=%s "
            "evaluation_status=%s "
            "errors=%s",
            request_id,
            faithfulness,
            answer_relevance,
            context_precision,
            context_recall,
            ragas_evaluated,
            evaluation_status,
            errors,
        )

        return result

    # ================================================================
    # PRODUCTION RAG REQUEST
    # ================================================================

    async def evaluate_rag_request(
        self,
        *,
        question: str,
        answer: str,
        retrieval_results: Any,
        reference: str | None = None,
        request_id: str = "unknown",
    ) -> dict[str, Any]:
        """
        Evaluate one production ERIS RAG request.
        """

        retrieved_contexts = self._extract_retrieved_contexts(retrieval_results)

        result_count = 0

        if isinstance(
            retrieval_results,
            (list, tuple),
        ):
            result_count = len(retrieval_results)

        logger.info(
            "RAGAS evaluate_rag_request "
            "request_id=%s retrieval_results=%d "
            "extracted_contexts=%d "
            "reference_present=%s",
            request_id,
            result_count,
            len(retrieved_contexts),
            bool(reference),
        )

        return await self.evaluate_case(
            question=question,
            answer=answer,
            retrieved_contexts=retrieved_contexts,
            reference=reference,
            request_id=request_id,
        )
