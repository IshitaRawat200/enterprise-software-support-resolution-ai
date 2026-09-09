from __future__ import annotations

from uuid import UUID

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.database.connection import get_db_session
from app.observability.logging import logger


async def mcp_validate_customer_account(
    customer_id: str,
) -> dict:
    """
    MCP tool for validating a customer account.

    Returns only safe, non-secret customer information.
    """

    try:
        UUID(customer_id)
    except ValueError:
        return {
            "success": False,
            "account_exists": False,
            "customer_id": customer_id,
            "error": "Invalid customer ID.",
        }

    query = text(
        """
        SELECT
            id,
            customer_code,
            company_name,
            contact_name,
            region,
            industry,
            account_status
        FROM customers
        WHERE id = CAST(:customer_id AS uuid)
        LIMIT 1
        """
    )

    try:
        async for db_session in get_db_session():
            result = await db_session.execute(
                query,
                {
                    "customer_id": customer_id,
                },
            )

            row = result.mappings().first()

            if row is None:
                return {
                    "success": True,
                    "account_exists": False,
                    "customer_id": customer_id,
                    "reason": ("Customer account was not found."),
                }

            return {
                "success": True,
                "account_exists": True,
                "customer_id": str(row["id"]),
                "customer_code": row["customer_code"],
                "company_name": row["company_name"],
                "contact_name": row["contact_name"],
                "region": row["region"],
                "industry": row["industry"],
                "account_status": row["account_status"],
            }

    except SQLAlchemyError:
        logger.exception("MCP customer account validation failed.")

        return {
            "success": False,
            "account_exists": False,
            "customer_id": customer_id,
            "error": "Account validation failed.",
        }

    return {
        "success": False,
        "account_exists": False,
        "customer_id": customer_id,
        "error": "Database session unavailable.",
    }
