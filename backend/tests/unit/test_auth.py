from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.guardrails.rbac import require_admin


@pytest.mark.asyncio
async def test_require_admin_allows_admin() -> None:
	current_user = SimpleNamespace(role="admin")

	result = await require_admin(current_user=current_user)

	assert result is current_user


@pytest.mark.asyncio
async def test_require_admin_blocks_non_admin() -> None:
	current_user = SimpleNamespace(role="support_agent")

	with pytest.raises(HTTPException) as exc_info:
		await require_admin(current_user=current_user)

	assert exc_info.value.status_code == 403
