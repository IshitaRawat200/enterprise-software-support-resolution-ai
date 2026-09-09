from types import SimpleNamespace
from uuid import UUID

import pytest
from fastapi import HTTPException

import app.api.customers as customers_api


class DummySession:
    pass


class FakeRepository:
    def __init__(self, session):
        self._session = session

    async def get_by_user_id(self, user_id):
        return None


class FakeRepositoryFound(FakeRepository):
    async def get_by_user_id(self, user_id):
        return SimpleNamespace(
            id=UUID("00000000-0000-0000-0000-000000000123"),
            customer_code="C123",
            company_name="Acme",
            contact_name="Bob",
            region="eu",
            industry="software",
            account_status="active",
        )


def test_get_my_customer_profile_not_found(monkeypatch):
    async def fake_get_db_session():
        if False:
            yield None
        yield DummySession()

    monkeypatch.setattr(customers_api, "get_db_session", fake_get_db_session)
    monkeypatch.setattr(customers_api, "CustomerRepository", FakeRepository)

    with pytest.raises(HTTPException) as exc:
        import asyncio

        asyncio.run(
            customers_api.get_my_customer_profile(
                current_user=SimpleNamespace(
                    id=UUID("00000000-0000-0000-0000-000000000999")
                ),
                session=DummySession(),
            )
        )

    assert exc.value.status_code == 404


def test_get_my_customer_profile_success(monkeypatch):
    async def fake_get_db_session():
        if False:
            yield None
        yield DummySession()

    monkeypatch.setattr(customers_api, "get_db_session", fake_get_db_session)
    monkeypatch.setattr(customers_api, "CustomerRepository", FakeRepositoryFound)

    import asyncio

    out = asyncio.run(
        customers_api.get_my_customer_profile(
            current_user=SimpleNamespace(
                id=UUID("00000000-0000-0000-0000-000000000123")
            ),
            session=DummySession(),
        )
    )

    # Pydantic model_validate returns a model instance with attributes
    assert out.customer_code == "C123"
    assert out.company_name == "Acme"
