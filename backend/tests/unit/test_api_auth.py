import asyncio
from types import SimpleNamespace

import app.api.auth as auth_api


def test_get_me_returns_user_response():
    user = SimpleNamespace(
        id="11111111-1111-1111-1111-111111111111",
        email="u@example.com",
        role="customer",
        is_active=True,
    )

    out = asyncio.run(auth_api.get_me(current_user=user))

    assert out.email == "u@example.com"
    assert out.role == "customer"


def test_login_success(monkeypatch):
    async def fake_authenticate_user(*args, **kwargs):
        return SimpleNamespace(id="1", role="customer")

    monkeypatch.setattr(auth_api, "authenticate_user", fake_authenticate_user)

    # Call login with a fake session (not used by our patched authenticate_user)
    request = SimpleNamespace(email="u@example.com", password="pw")

    out = asyncio.run(auth_api.login(request=request, session=None))

    assert hasattr(out, "access_token")
    assert out.token_type == "bearer"
