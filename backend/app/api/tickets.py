from __future__ import annotations

from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.connection import get_db_session
from app.database.models.user import User
from app.database.repositories.customers import CustomerRepository
from app.guardrails.rbac import require_customer
from app.schemas.ticket import (
    TicketCreateRequest,
    TicketMessageCreateRequest,
    TicketMessageResponse,
    TicketResponse,
)
from app.services.ticket_service import (
    add_customer_message,
    create_customer_ticket,
    get_customer_ticket,
    list_customer_tickets,
)


router = APIRouter(
    prefix="/tickets",
    tags=["Tickets"],
)


@router.post("", response_model=TicketResponse, status_code=status.HTTP_201_CREATED)
async def create_ticket(
    request: TicketCreateRequest,
    current_user: User = Depends(require_customer),
    session: AsyncSession = Depends(get_db_session),
) -> TicketResponse:

    customer_repository = CustomerRepository(session)

    customer = await customer_repository.get_by_user_id(current_user.id)

    if customer is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Customer profile not found.",
        )

    ticket = await create_customer_ticket(
        session=session,
        customer=customer,
        subject=request.subject,
        description=request.description,
    )

    return TicketResponse.model_validate(ticket)


@router.get(
    "",
    response_model=list[TicketResponse],
)
async def list_my_tickets(
    current_user: User = Depends(require_customer),
    session: AsyncSession = Depends(get_db_session),
) -> list[TicketResponse]:

    customer_repository = CustomerRepository(session)

    customer = await customer_repository.get_by_user_id(
        current_user.id
    )

    if customer is None:
        from fastapi import HTTPException

        raise HTTPException(
            status_code=404,
            detail="Customer profile not found.",
        )

    tickets = await list_customer_tickets(
        session=session,
        customer_id=customer.id,
    )

    return [
        TicketResponse.model_validate(ticket)
        for ticket in tickets
    ]


@router.get(
    "/{ticket_id}",
    response_model=TicketResponse,
)
async def get_my_ticket(
    ticket_id: UUID,
    current_user: User = Depends(require_customer),
    session: AsyncSession = Depends(get_db_session),
) -> TicketResponse:

    customer_repository = CustomerRepository(session)

    customer = await customer_repository.get_by_user_id(
        current_user.id
    )

    if customer is None:
        from fastapi import HTTPException

        raise HTTPException(
            status_code=404,
            detail="Customer profile not found.",
        )

    ticket = await get_customer_ticket(
        session=session,
        customer_id=customer.id,
        ticket_id=ticket_id,
    )

    return TicketResponse.model_validate(ticket)


@router.post(
    "/{ticket_id}/messages",
    response_model=TicketMessageResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_ticket_message(
    ticket_id: UUID,
    request: TicketMessageCreateRequest,
    current_user: User = Depends(require_customer),
    session: AsyncSession = Depends(get_db_session),
) -> TicketMessageResponse:

    customer_repository = CustomerRepository(session)

    customer = await customer_repository.get_by_user_id(
        current_user.id
    )

    if customer is None:
        from fastapi import HTTPException

        raise HTTPException(
            status_code=404,
            detail="Customer profile not found.",
        )

    message = await add_customer_message(
        session=session,
        customer_id=customer.id,
        ticket_id=ticket_id,
        user_id=current_user.id,
        message_text=request.message,
    )

    return TicketMessageResponse.model_validate(message)