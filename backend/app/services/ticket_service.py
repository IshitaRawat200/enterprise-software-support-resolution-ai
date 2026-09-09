from __future__ import annotations

from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.database.repositories.audit_repository import AuditRepository
from app.database.repositories.ticket_message_repository import (
    TicketMessageRepository,
)
from app.database.repositories.ticket_repository import TicketRepository


class TicketService:
    """Business logic for AI-created and customer-managed tickets."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.tickets = TicketRepository(session)
        self.messages = TicketMessageRepository(session)
        self.audit = AuditRepository(session)

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
    ):
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

    @staticmethod
    def _build_subject(message: str) -> str:
        cleaned = " ".join(message.split())

        if len(cleaned) <= 120:
            return cleaned

        return f"{cleaned[:117]}..."
