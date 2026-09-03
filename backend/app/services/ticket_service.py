from __future__ import annotations

from uuid import UUID, uuid4

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.ticket import SupportTicket
from app.database.models.ticket_message import TicketMessage
from app.database.repositories.tickets import TicketRepository


def generate_ticket_number() -> str:
    return f"TK-{uuid4().hex[:8].upper()}"


async def create_customer_ticket(
    session: AsyncSession,
    customer,
    subject: str,
    description: str,
) -> SupportTicket:
    repository = TicketRepository(session)

    ticket = SupportTicket(
        ticket_number=generate_ticket_number(),
        customer_id=customer.id,
        subject=subject.strip(),
        description=description.strip(),
        status="open",
        severity="medium",
        escalation_required=False,
    )

    ticket = await repository.create(ticket)

    message = TicketMessage(
        ticket_id=ticket.id,
        sender_type="customer",
        sender_user_id=None,
        message=description.strip(),
    )

    await repository.add_message(message)

    await session.commit()
    await session.refresh(ticket)

    return ticket


async def list_customer_tickets(
    session: AsyncSession,
    customer_id: UUID,
) -> list[SupportTicket]:
    repository = TicketRepository(session)

    return await repository.list_by_customer(customer_id)


async def get_customer_ticket(
    session: AsyncSession,
    customer_id: UUID,
    ticket_id: UUID,
) -> SupportTicket:
    repository = TicketRepository(session)

    ticket = await repository.get_by_id(ticket_id)

    if ticket is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ticket not found.",
        )

    if ticket.customer_id != customer_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this ticket.",
        )

    return ticket


async def add_customer_message(
    session: AsyncSession,
    customer_id: UUID,
    ticket_id: UUID,
    user_id: UUID,
    message_text: str,
) -> TicketMessage:
    repository = TicketRepository(session)

    ticket = await repository.get_by_id(ticket_id)

    if ticket is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ticket not found.",
        )

    if ticket.customer_id != customer_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this ticket.",
        )

    if ticket.status in {"resolved", "closed"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot add messages to a resolved or closed ticket.",
        )

    message = TicketMessage(
        ticket_id=ticket.id,
        sender_type="customer",
        sender_user_id=user_id,
        message=message_text.strip(),
    )

    message = await repository.add_message(message)

    await session.commit()
    await session.refresh(message)

    return message