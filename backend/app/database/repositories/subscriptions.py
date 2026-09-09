from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.subscription import Subscription


class SubscriptionRepository:
    """Database operations for subscriptions."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(
        self,
        subscription_id: UUID,
    ) -> Subscription | None:
        result = await self.session.execute(
            select(Subscription).where(Subscription.id == subscription_id)
        )
        return result.scalar_one_or_none()

    async def get_by_customer_id(
        self,
        customer_id: UUID,
    ) -> list[Subscription]:
        result = await self.session.execute(
            select(Subscription)
            .where(Subscription.customer_id == customer_id)
            .order_by(Subscription.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_active_by_customer_id(
        self,
        customer_id: UUID,
    ) -> Subscription | None:
        result = await self.session.execute(
            select(Subscription)
            .where(
                Subscription.customer_id == customer_id,
                Subscription.status == "active",
            )
            .order_by(Subscription.created_at.desc())
        )
        return result.scalars().first()
