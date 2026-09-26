from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.database.repositories.conversation_repository import ConversationRepository


class ConversationService:
    """Application service for conversation persistence."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = ConversationRepository(session)

    @staticmethod
    def create_session_id() -> UUID:
        return uuid4()

    async def list_sessions(self, *, user_id: UUID, limit: int = 10) -> list[dict[str, Any]]:
        return await self.repository.list_sessions(user_id=user_id, limit=limit)

    async def get_history(self, *, session_id: UUID, user_id: UUID) -> list[Any]:
        return await self.repository.get_history(session_id=session_id, user_id=user_id)

    async def add_customer_message(self, *, session_id: UUID, user_id: UUID, content: str, metadata: dict[str, Any] | None = None, ticket_id: UUID | None = None):
        return await self.repository.add_customer_message(session_id=session_id, user_id=user_id, content=content, metadata=metadata, ticket_id=ticket_id)

    async def add_ai_message(self, *, session_id: UUID, user_id: UUID, content: str, metadata: dict[str, Any] | None = None, ticket_id: UUID | None = None):
        return await self.repository.add_ai_message(session_id=session_id, user_id=user_id, content=content, metadata=metadata, ticket_id=ticket_id)

    async def add_support_agent_message(self, *, session_id: UUID, user_id: UUID, content: str, metadata: dict[str, Any] | None = None, ticket_id: UUID | None = None, sender_user_id: UUID | None = None):
        return await self.repository.add_support_agent_message(session_id=session_id, user_id=user_id, content=content, metadata=metadata, ticket_id=ticket_id, sender_user_id=sender_user_id)

    async def get_ai_message_metadata_by_request_id_for_user(self, *, request_id: str, user_id: UUID) -> dict[str, Any] | None:
        message = await self.repository.get_ai_message_by_request_id_for_user(
            request_id=request_id,
            user_id=user_id,
        )

        if message is None:
            return None

        metadata = getattr(message, "metadata_", {})

        if not isinstance(metadata, dict):
            return {}

        return dict(metadata)

    async def update_ai_message_evaluation(self, *, request_id: str, evaluation: dict[str, Any]) -> None:
        message = await self.repository.get_ai_message_by_request_id(request_id=request_id)
        if message is None:
            raise ValueError("AI message not found for request_id.")

        existing = getattr(message, "metadata_", {})
        updated = dict(existing) if isinstance(existing, dict) else {}

        ragas_evaluated = bool(evaluation.get("ragas_evaluated", False))
        errors = evaluation.get("ragas_errors", [])
        if not isinstance(errors, list):
            errors = [str(errors)]

        values = {
            "faithfulness": evaluation.get("faithfulness"),
            "answer_relevance": evaluation.get("answer_relevance"),
            "context_precision": evaluation.get("context_precision"),
            "context_recall": evaluation.get("context_recall"),
            "route_accuracy": evaluation.get("route_accuracy"),
            "ragas_evaluated": ragas_evaluated,
            "ragas_errors": errors,
        }

        values["accuracy"] = self._compute_accuracy(values)

        requested_status = evaluation.get("evaluation_status")

        if requested_status in {"completed", "partial", "failed"}:
            status = str(requested_status)
        elif ragas_evaluated:
            status = "completed"
        else:
            status = "failed"

        updated.update({"evaluation_status": status, **values})

        nested = updated.get("evaluation")
        evaluation_metadata = dict(nested) if isinstance(nested, dict) else {}
        evaluation_metadata.update({"status": status, **values})
        updated["evaluation"] = evaluation_metadata

        await self.repository.update_message_metadata(message=message, metadata=updated)

    @staticmethod
    def _compute_accuracy(values: dict[str, Any]) -> float | None:
        score_fields = (
            "faithfulness",
            "answer_relevance",
            "context_precision",
            "context_recall",
            "route_accuracy",
        )

        normalized_scores: list[float] = []

        for field in score_fields:
            value = values.get(field)

            if value is None or isinstance(value, bool):
                continue

            try:
                score = float(value)
            except (TypeError, ValueError):
                continue

            # RAGAS metrics are [0, 1], while route_accuracy is [0, 100].
            if score > 1.0:
                score = score / 100.0

            score = max(0.0, min(1.0, score))
            normalized_scores.append(score)

        if not normalized_scores:
            return None

        return sum(normalized_scores) / len(normalized_scores)

    async def link_session_to_ticket(self, *, session_id: UUID, user_id: UUID, ticket_id: UUID) -> int:
        return await self.repository.link_session_to_ticket(session_id=session_id, user_id=user_id, ticket_id=ticket_id)