from __future__ import annotations

from typing import Callable

from fastapi import Depends, HTTPException, status

from app.database.models.user import User
from app.guardrails.auth import get_current_user


def require_role(required_role: str) -> Callable:
    async def role_dependency(
        current_user: User = Depends(get_current_user),
    ) -> User:
        if current_user.role != required_role:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions.",
            )

        return current_user

    return role_dependency


require_customer = require_role("customer")

require_support_agent = require_role("support_agent")