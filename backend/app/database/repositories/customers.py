from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.customer import Customer


class CustomerRepository:
    """Database operations for customers."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(
        self,
        customer_id: UUID,
    ) -> Customer | None:
        result = await self.session.execute(
            select(Customer).where(
                Customer.id == customer_id
            )
        )

        return result.scalar_one_or_none()

    async def get_by_user_id(
        self,
        user_id: UUID,
    ) -> Customer | None:
        result = await self.session.execute(
            select(Customer).where(
                Customer.user_id == user_id
            )
        )

        return result.scalar_one_or_none()

    async def get_by_customer_code(
        self,
        customer_code: str,
    ) -> Customer | None:
        result = await self.session.execute(
            select(Customer).where(
                Customer.customer_code == customer_code
            )
        )

        return result.scalar_one_or_none()

    async def create(
        self,
        customer: Customer,
    ) -> Customer:
        self.session.add(customer)

        await self.session.flush()
        await self.session.refresh(customer)

        return customer