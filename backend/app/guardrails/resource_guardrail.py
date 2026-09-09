from __future__ import annotations

from typing import Any

from app.guardrails.guardrail_result import GuardrailResult

GUARDRAIL_NAME = "resource_guardrail"

PRIVILEGED_ROLES = {
    "admin",
    "support_agent",
}


def _normalize_role(
    role: Any,
) -> str:
    return str(role or "").strip().lower()


def can_access_customer(
    *,
    current_user: Any,
    customer_id: str | None,
) -> GuardrailResult:
    """
    Determine whether the authenticated user may access
    a customer's data.

    Rules:

    admin/support_agent:
        allowed to access customer resources according
        to the application's support authorization policy.

    customer:
        may access only their own customer resource.

    Important:
        The caller must provide the authoritative customer_id
        associated with the customer user. Do not trust a
        customer_id supplied directly by the browser.
    """

    if current_user is None:
        return GuardrailResult.block(
            GUARDRAIL_NAME,
            reason="Authenticated user is required.",
            risk_level="high",
            code="USER_NOT_AUTHENTICATED",
        )

    if not customer_id:
        return GuardrailResult.block(
            GUARDRAIL_NAME,
            reason="Customer identifier is required.",
            risk_level="medium",
            code="CUSTOMER_ID_MISSING",
        )

    role = _normalize_role(getattr(current_user, "role", None))

    # --------------------------------------------------------
    # Privileged support access
    # --------------------------------------------------------

    if role in PRIVILEGED_ROLES:
        return GuardrailResult.allow(
            GUARDRAIL_NAME,
            reason="Privileged support role may access customer resource.",
            metadata={
                "role": role,
                "customer_id": str(customer_id),
            },
        )

    # --------------------------------------------------------
    # Customer self-access
    # --------------------------------------------------------

    if role == "customer":
        own_customer_id = getattr(
            current_user,
            "customer_id",
            None,
        )

        if own_customer_id is None:
            return GuardrailResult.block(
                GUARDRAIL_NAME,
                reason=(
                    "Customer user is not associated with "
                    "an authorized customer account."
                ),
                risk_level="high",
                code="CUSTOMER_ACCOUNT_MISSING",
            )

        if str(own_customer_id) != str(customer_id):
            return GuardrailResult.block(
                GUARDRAIL_NAME,
                reason="Customer is not authorized to access this resource.",
                risk_level="critical",
                code="CROSS_CUSTOMER_ACCESS",
                metadata={
                    "role": role,
                },
            )

        return GuardrailResult.allow(
            GUARDRAIL_NAME,
            reason="Customer is accessing their own resource.",
        )

    # --------------------------------------------------------
    # Unknown role
    # --------------------------------------------------------

    return GuardrailResult.block(
        GUARDRAIL_NAME,
        reason=f"Role '{role}' is not authorized for customer access.",
        risk_level="high",
        code="ROLE_NOT_AUTHORIZED",
        metadata={
            "role": role,
        },
    )


def can_access_ticket(
    *,
    current_user: Any,
    ticket_customer_id: str | None,
) -> GuardrailResult:
    """
    Ticket-level authorization follows the same customer
    resource boundary.
    """

    return can_access_customer(
        current_user=current_user,
        customer_id=ticket_customer_id,
    )
