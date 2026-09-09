from __future__ import annotations

from fastapi import Depends, HTTPException, status

from app.guardrails.auth import get_current_user

# Module-level dependency object to avoid calling Depends() in
# argument defaults (satisfies ruff B008).
get_current_user_dep = Depends(get_current_user)


def require_role(*allowed_roles: str):

    async def role_checker(
        current_user=get_current_user_dep,
    ):

        user_role = str(current_user.role)

        if user_role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions.",
            )

        return current_user

    return role_checker


require_admin = require_role("admin")

require_support_agent = require_role(
    "support_agent",
    "admin",
)

require_customer = require_role(
    "customer",
)
