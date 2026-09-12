from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.account.account_validation_schema import (
    AccountValidationResult,
)
from app.database.repositories.customers import CustomerRepository


class AccountValidationAgent:
    """
    Account Validation Agent.

    Responsibilities:

    1. Validate that the customer account exists.
    2. Retrieve trusted account information.
    3. Return structured account evidence.
    4. Avoid exposing raw SQL or private reasoning.

    This agent uses controlled repository methods rather
    than allowing an LLM to directly query the database.
    """

    agent_name = "account_validation_agent"

    async def validate(
        self,
        session: AsyncSession,
        customer_id: UUID,
    ) -> AccountValidationResult:

        if not customer_id:
            raise ValueError("Customer ID is required.")

        repository = CustomerRepository(session)

        customer = await repository.get_by_id(customer_id)

        # Customer does not exist.
        if customer is None:
            return AccountValidationResult(
                customer_id=customer_id,
                account_exists=False,
                account_status="unknown",
                validation_confidence=1.0,
                reason=("No customer account was found for the supplied customer ID."),
            )

        # Customer exists.
        return AccountValidationResult(
            customer_id=customer.id,
            account_exists=True,
            account_status=customer.account_status,
            company_name=customer.company_name,
            contact_name=customer.contact_name,
            region=customer.region,
            industry=customer.industry,
            validation_confidence=1.0,
            reason=(
                "Customer account information was "
                "successfully validated against "
                "the application database."
            ),
        )
