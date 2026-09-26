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
from app.guardrails.rbac import (
    require_customer_or_admin,
)
from app.schemas.ticket import TicketResponse
from app.services.ticket_service import TicketService

router = APIRouter(
    prefix="/tickets",
    tags=["Tickets"],
)


# ============================================================
# DEPENDENCIES
# ============================================================

require_customer_or_admin_dep = Depends(
    require_customer_or_admin
)

get_db_session_dep = Depends(
    get_db_session
)


# ============================================================
# CUSTOMER LOOKUP
# ============================================================

async def get_current_customer(
    current_user: User,
    session: AsyncSession,
):
    customer_repository = CustomerRepository(
        session
    )

    customer = (
        await customer_repository.get_by_user_id(
            current_user.id
        )
    )

    if customer is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Customer profile not found.",
        )

    return customer


# ============================================================
# LIST TICKETS
# ============================================================

@router.get(
    "",
    response_model=list[TicketResponse],
)
async def list_tickets(
    current_user: User = require_customer_or_admin_dep,
    session: AsyncSession = get_db_session_dep,
) -> list[TicketResponse]:

    service = TicketService(session)

    # --------------------------------------------------------
    # ADMIN
    # --------------------------------------------------------

    if str(current_user.role) == "admin":
        tickets = await service.list_all_tickets()

        return [
            TicketResponse.model_validate(ticket)
            for ticket in tickets
        ]

    # --------------------------------------------------------
    # CUSTOMER
    # --------------------------------------------------------

    customer = await get_current_customer(
        current_user,
        session,
    )

    tickets = await service.list_customer_tickets(
        customer_id=customer.id,
    )

    return [
        TicketResponse.model_validate(ticket)
        for ticket in tickets
    ]


# ============================================================
# GET SINGLE TICKET
# ============================================================

@router.get(
    "/{ticket_id}",
    response_model=TicketResponse,
)
async def get_ticket(
    ticket_id: UUID,
    current_user: User = require_customer_or_admin_dep,
    session: AsyncSession = get_db_session_dep,
) -> TicketResponse:

    service = TicketService(session)

    # --------------------------------------------------------
    # ADMIN
    # --------------------------------------------------------

    if str(current_user.role) == "admin":
        try:
            ticket = await service.get_ticket(
                ticket_id=ticket_id,
            )

        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(exc),
            ) from exc

        return TicketResponse.model_validate(
            ticket
        )

    # --------------------------------------------------------
    # CUSTOMER
    # --------------------------------------------------------

    customer = await get_current_customer(
        current_user,
        session,
    )

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

    return TicketResponse.model_validate(
        ticket
    )