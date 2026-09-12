from __future__ import annotations

from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.database.repositories.audit_repository import AuditRepository
from app.database.repositories.ticket_message_repository import (
    TicketMessageRepository,
)
from app.database.repositories.ticket_repository import TicketRepository
from app.guardrails.handoff_guardrail import detect_explicit_human_request
from app.services.conversation_service import ConversationService
from app.services.escalation_service import EscalationService


class TicketService:
    """Business logic for AI-created and customer-managed tickets."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.tickets = TicketRepository(session)
        self.messages = TicketMessageRepository(session)
        self.audit = AuditRepository(session)
        self.conversation = ConversationService(session)

    @staticmethod
    def generate_ticket_number() -> str:
        return f"TCK-{uuid4().hex[:8].upper()}"

    async def find_active_ticket(
        self,
        *,
        customer_id: UUID,
    ):
        return await self.tickets.find_active_for_customer(
            customer_id,
        )

    async def list_customer_tickets(
        self,
        *,
        customer_id: UUID,
    ):
        return await self.tickets.list_by_customer(
            customer_id,
        )

    async def get_customer_ticket(
        self,
        *,
        customer_id: UUID,
        ticket_id: UUID,
    ):
        ticket = await self.tickets.get_by_id(ticket_id)

        if ticket is None:
            raise ValueError("Ticket not found.")

        if ticket.customer_id != customer_id:
            raise PermissionError(
                "Customer does not own this ticket.",
            )

        return ticket

    async def create_customer_ticket(
        self,
        *,
        customer_id: UUID,
        subject: str,
        description: str,
        severity: str = "medium",
        request_id: UUID | None = None,
        commit: bool = True,
    ):
        ticket = await self.tickets.create(
            ticket_number=self.generate_ticket_number(),
            customer_id=customer_id,
            subject=subject,
            description=description,
            intent=None,
            route=None,
            severity=severity,
            confidence=None,
            escalation_required=False,
            escalation_reason=None,
            ai_investigation_summary=None,
        )

        await self.messages.create(
            ticket_id=ticket.id,
            sender_type="customer",
            sender_user_id=None,
            message=description,
        )

        if request_id is not None:
            await self.audit.create(
                request_id=request_id,
                event_type="CUSTOMER_CREATED_TICKET",
                actor="customer",
                action="create_ticket",
                user_id=None,
                session_id=None,
                ticket_id=ticket.id,
                details={
                    "severity": severity,
                },
            )

        if commit:
            await self.session.commit()

        return ticket

    async def create_ai_ticket(
        self,
        *,
        customer_id: UUID,
        message: str,
        intent: str | None,
        route: str | None,
        severity: str,
        confidence: float | None,
        escalation_required: bool,
        escalation_reason: str | None,
        ai_investigation_summary: str | None,
        request_id: UUID,
        session_id: UUID | None = None,
        commit: bool = True,
    ):
        explicit_human_handoff = (
            bool(escalation_required)
            and (
                intent == "human_handoff"
                or detect_explicit_human_request(message)["trigger"]
            )
        )

        existing = None
        if not explicit_human_handoff:
            existing = await self.find_active_ticket(
                customer_id=customer_id,
            )

        if existing is not None:
            return await self.update_ai_ticket(
                ticket=existing,
                message=message,
                intent=intent,
                route=route,
                severity=severity,
                confidence=confidence,
                escalation_required=escalation_required,
                escalation_reason=escalation_reason,
                ai_investigation_summary=ai_investigation_summary,
                request_id=request_id,
                session_id=session_id,
                commit=commit,
            )

        ticket = await self.tickets.create(
            ticket_number=self.generate_ticket_number(),
            customer_id=customer_id,
            subject=self._build_subject(message),
            description=message,
            intent=intent,
            route=route,
            severity=severity,
            confidence=confidence,
            escalation_required=escalation_required,
            escalation_reason=escalation_reason,
            ai_investigation_summary=ai_investigation_summary,
        )

        await self.messages.create(
            ticket_id=ticket.id,
            sender_type="customer",
            sender_user_id=None,
            message=message,
        )

        await self.audit.create(
            request_id=request_id,
            event_type="AI_CREATED_TICKET",
            actor="ai",
            action="create_ticket",
            user_id=None,
            session_id=session_id,
            ticket_id=ticket.id,
            details={
                "severity": severity,
                "intent": intent,
                "route": route,
                "escalation_required": escalation_required,
            },
        )

        if commit:
            await self.session.commit()

        return ticket

    async def update_ai_ticket(
        self,
        *,
        ticket,
        message: str,
        intent: str | None,
        route: str | None,
        severity: str,
        confidence: float | None,
        escalation_required: bool,
        escalation_reason: str | None,
        ai_investigation_summary: str | None,
        request_id: UUID,
        session_id: UUID | None = None,
        commit: bool = True,
    ):
        await self.tickets.update(
            ticket,
            {
                "intent": intent,
                "route": route,
                "severity": severity,
                "confidence": confidence,
                "escalation_required": escalation_required,
                "escalation_reason": escalation_reason,
                "ai_investigation_summary": ai_investigation_summary,
            },
        )

        await self.messages.create(
            ticket_id=ticket.id,
            sender_type="customer",
            sender_user_id=None,
            message=message,
        )

        await self.audit.create(
            request_id=request_id,
            event_type="AI_UPDATED_TICKET",
            actor="ai",
            action="update_ticket",
            session_id=session_id,
            ticket_id=ticket.id,
            details={
                "severity": severity,
                "intent": intent,
                "route": route,
                "escalation_required": escalation_required,
            },
        )

        if commit:
            await self.session.commit()

        return ticket

    async def add_customer_message(
        self,
        *,
        ticket_id: UUID,
        customer_id: UUID,
        message: str,
        request_id: UUID,
        user_id: UUID | None = None,
    ):
        ticket = await self.tickets.get_by_id(ticket_id)

        if ticket is None:
            raise ValueError("Ticket not found.")

        if ticket.customer_id != customer_id:
            raise PermissionError(
                "Customer does not own this ticket.",
            )

        ticket_message = await self.messages.create(
            ticket_id=ticket_id,
            sender_type="customer",
            sender_user_id=user_id,
            message=message,
        )

        await self.audit.create(
            request_id=request_id,
            event_type="CUSTOMER_MESSAGE_ADDED",
            actor="customer",
            action="add_ticket_message",
            user_id=user_id,
            session_id=None,
            ticket_id=ticket_id,
            details={},
        )

        await self.session.commit()

        return ticket_message

    async def link_session_to_ticket(
        self,
        *,
        session_id: UUID,
        user_id: UUID,
        ticket_id: UUID,
    ) -> int:
        return await self.conversation.link_session_to_ticket(
            session_id=session_id,
            user_id=user_id,
            ticket_id=ticket_id,
        )

    async def persist_ticket_and_escalation(
        self,
        *,
        customer_id: UUID,
        message: str,
        intent: str | None,
        route: str | None,
        severity: str,
        confidence: float | None,
        escalation_required: bool,
        escalation_reason: str | None,
        ai_investigation_summary: str | None,
        request_id: UUID,
        session_id: UUID | None = None,
        user_id: UUID | None = None,
        handoff_context: dict[str, object] | None = None,
        handoff_summary: str | None = None,
        recommended_action: str | None = None,
    ) -> dict[str, object]:
        ticket = await self.create_ai_ticket(
            customer_id=customer_id,
            message=message,
            intent=intent,
            route=route,
            severity=severity,
            confidence=confidence,
            escalation_required=escalation_required,
            escalation_reason=escalation_reason,
            ai_investigation_summary=ai_investigation_summary,
            request_id=request_id,
            session_id=session_id,
            commit=False,
        )

        handoff_context = dict(handoff_context or {})

        priority = handoff_context.get("priority")
        escalation_type = handoff_context.get("type") or handoff_context.get(
            "escalation_type"
        )

        if not priority and escalation_required:
            priority = "high"

        if not escalation_type and escalation_required:
            escalation_type = "human_requested"

        if handoff_context.get("priority") is None and priority is not None:
            handoff_context["priority"] = priority

        if handoff_context.get("type") is None and escalation_type is not None:
            handoff_context["type"] = escalation_type

        if handoff_context.get("escalation_type") is None and escalation_type is not None:
            handoff_context["escalation_type"] = escalation_type

        explicit_human_request = detect_explicit_human_request(message)["trigger"]
        if (
            escalation_required
            and (
                explicit_human_request
                or intent == "human_handoff"
                or (isinstance(handoff_context, dict) and handoff_context.get("type") == "human_requested")
            )
        ):
            escalation_reason_text = "Customer explicitly requested human support intervention."
        else:
            escalation_reason_text = escalation_reason or "Human intervention required."

        escalation_result = {
            "id": None,
            "reason": escalation_reason_text,
            "severity": severity or "low",
            "priority": priority,
            "type": escalation_type,
            "confidence": confidence,
            "handoff_package": {
                "priority": priority,
                "type": escalation_type,
                "summary": handoff_summary,
                "recommended_action": recommended_action,
                "context": handoff_context,
                "customer_id": str(customer_id),
                "conversation_id": str(session_id) if session_id else None,
            },
            "investigation_summary": (
                ai_investigation_summary or handoff_summary or recommended_action
            ),
        }

        if escalation_required:
            escalation = await EscalationService.create_or_update(
                session=self.session,
                ticket_id=ticket.id,
                reason=escalation_result["reason"],
                severity=escalation_result["severity"],
                confidence=confidence,
                handoff_package=escalation_result["handoff_package"],
                investigation_summary=escalation_result["investigation_summary"],
            )
            escalation_result["id"] = escalation.id

        if session_id is not None and user_id is not None:
            await self.link_session_to_ticket(
                session_id=session_id,
                user_id=user_id,
                ticket_id=ticket.id,
            )

        await self.session.commit()

        return {
            "ticket_id": ticket.id,
            "ticket_number": ticket.ticket_number,
            "escalation_required": escalation_required,
            "human_handoff_required": escalation_required,
            "escalation_id": escalation_result["id"],
            "escalation_reason": escalation_result["reason"],
            "escalation_priority": escalation_result["priority"],
            "escalation_type": escalation_result["type"],
            "handoff_context": {
                **escalation_result["handoff_package"],
                "priority": escalation_result["priority"],
                "type": escalation_result["type"],
                "escalation_type": escalation_result["type"],
            },
            "handoff_summary": handoff_summary,
            "recommended_action": recommended_action,
        }

    @staticmethod
    def _build_subject(message: str) -> str:
        cleaned = " ".join((message or "").split())

        if not cleaned:
            return "Support Request"

        if detect_explicit_human_request(cleaned)["trigger"]:
            return "Human Support Request"

        if len(cleaned) <= 120:
            return cleaned

        return f"{cleaned[:117]}..."
