import os
from types import SimpleNamespace

from fastapi.testclient import TestClient


# Ensure a DATABASE_URL exists before importing the application.
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://testuser:testpass@localhost/testdb",
)


def _patch_auth_for_tests(monkeypatch):
    import app.main as main
    import app.api.auth as auth_api

    # ---------------------------------------------------------
    # Disable expensive startup dependencies
    # ---------------------------------------------------------

    # No-op embedding preload.
    monkeypatch.setattr(main, "get_embedding_model", lambda: None)

    # Fake LangGraph PostgreSQL checkpointer.
    async def _fake_from_conn_string(conn_str: str):
        class _FakeCheckpointer:
            async def setup(self):
                return None

        yield _FakeCheckpointer()

    monkeypatch.setattr(
        main.AsyncPostgresSaver,
        "from_conn_string",
        _fake_from_conn_string,
        raising=False,
    )

    # ---------------------------------------------------------
    # Mock authentication
    # ---------------------------------------------------------

    async def _fake_authenticate_user(
        repository,
        email,
        password,
    ):
        return SimpleNamespace(
            id="user-1",
            email=email,
        )

    def _fake_create_access_token(user):
        return ("fake-token", 3600)

    # IMPORTANT:
    # app.api.auth imported these functions directly, so patch
    # the names used by the endpoint, not only the service module.
    auth_api.authenticate_user = _fake_authenticate_user
    auth_api.create_access_token = _fake_create_access_token

    # ---------------------------------------------------------
    # Mock database health check
    # ---------------------------------------------------------

    import app.database.connection as db_conn

    async def _always_true():
        return True

    db_conn.check_database_connection = _always_true
    main.check_database_connection = _always_true

    return main


def test_login_returns_token(monkeypatch):
    main = _patch_auth_for_tests(monkeypatch)

    client = TestClient(main.app)

    payload = {
        "email": "test@example.com",
        "password": "secret",
    }

    response = client.post(
        "/auth/login",
        json=payload,
    )

    assert response.status_code == 200

    body = response.json()

    assert body["access_token"] == "fake-token"

    assert body["token_type"] == "bearer"
