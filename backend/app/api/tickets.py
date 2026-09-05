from __future__ import annotations

from uuid import UUID, uuid4

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
from app.services.ticket_service import TicketService


router = APIRouter(
    prefix="/tickets",
    tags=["Tickets"],
)


async def get_current_customer(
    current_user: User,
    session: AsyncSession,
):
    customer_repository = CustomerRepository(session)

    customer = await customer_repository.get_by_user_id(
        current_user.id
    )

    if customer is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Customer profile not found.",
        )

    return customer


@router.post(
    "",
    response_model=TicketResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_ticket(
    request: TicketCreateRequest,
    current_user: User = Depends(require_customer),
    session: AsyncSession = Depends(get_db_session),
) -> TicketResponse:
    customer = await get_current_customer(
        current_user,
        session,
    )

    service = TicketService(session)

    ticket = await service.create_customer_ticket(
        customer_id=customer.id,
        subject=request.subject,
        description=request.description,
        severity=request.severity,
        request_id=uuid4(),
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
    customer = await get_current_customer(
        current_user,
        session,
    )

    service = TicketService(session)

    tickets = await service.list_customer_tickets(
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
    customer = await get_current_customer(
        current_user,
        session,
    )

    service = TicketService(session)

    try:
        ticket = await service.get_customer_ticket(
            customer_id=customer.id,
            ticket_id=ticket_id,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except PermissionError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc

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
    customer = await get_current_customer(
        current_user,
        session,
    )

    service = TicketService(session)

    try:
        message = await service.add_customer_message(
            ticket_id=ticket_id,
            customer_id=customer.id,
            message=request.message,
            request_id=uuid4(),
            user_id=current_user.id,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except PermissionError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc

    return TicketMessageResponse.model_validate(message)