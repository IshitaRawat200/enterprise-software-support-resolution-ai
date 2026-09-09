import asyncio
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.services import auth_service
from app.services.auth_service import (
    authenticate_user,
    create_access_token,
    normalize_email,
    verify_password,
)


def test_normalize_email():
    assert normalize_email("  USER@Example.COM ") == "user@example.com"


def test_password_hash_and_verify():
    pw = "s3cret"
    hashed = auth_service.hash_password(pw)
    assert verify_password(pw, hashed) is True
    assert verify_password("wrong", hashed) is False


def test_create_access_token():
    user = SimpleNamespace(id="11111111-1111-1111-1111-111111111111", role="customer")

    token, expires_in = create_access_token(user)

    assert isinstance(token, str)
    assert isinstance(expires_in, int)


def test_authenticate_user_success_and_failures():
    class FakeRepo:
        def __init__(self, user):
            self._user = user

        async def get_by_email(self, email):
            return self._user

    # successful auth
    user = SimpleNamespace(
        id="1",
        password_hash=auth_service.hash_password("pw"),
        is_active=True,
        role="customer",
    )
    repo = FakeRepo(user)

    res = asyncio.run(authenticate_user(repo, "user@example.com", "pw"))
    assert res == user

    # not found
    repo2 = FakeRepo(None)
    with pytest.raises(HTTPException) as excinfo:
        asyncio.run(authenticate_user(repo2, "x@x.com", "pw"))
    assert "Invalid email or password" in str(excinfo.value.detail)

    # inactive user
    user_inactive = SimpleNamespace(
        id="2",
        password_hash=auth_service.hash_password("pw"),
        is_active=False,
        role="customer",
    )
    repo3 = FakeRepo(user_inactive)
    with pytest.raises(HTTPException) as excinfo:
        asyncio.run(authenticate_user(repo3, "user@example.com", "pw"))
    assert "inactive" in str(excinfo.value.detail).lower()

    # wrong password
    user2 = SimpleNamespace(
        id="3",
        password_hash=auth_service.hash_password("pw"),
        is_active=True,
        role="customer",
    )
    repo4 = FakeRepo(user2)
    with pytest.raises(HTTPException) as excinfo:
        asyncio.run(authenticate_user(repo4, "user@example.com", "badpw"))
    assert "Invalid email or password" in str(excinfo.value.detail)
