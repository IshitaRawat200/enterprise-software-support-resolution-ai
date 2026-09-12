import os
from contextlib import asynccontextmanager

from fastapi.testclient import TestClient

# Ensure a DATABASE_URL exists so the app lifespan can start in tests
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://testuser:testpass@localhost/testdb",
)


def _patch_app_for_tests(monkeypatch):
    """Patch heavy startup dependencies to keep e2e tests deterministic."""

    # Import here so we can patch before the TestClient starts the lifespan
    from app import main

    # No-op the embedding model preload
    monkeypatch.setattr(main, "get_embedding_model", lambda: None)

    # Replace AsyncPostgresSaver.from_conn_string with a no-op async context
    @asynccontextmanager
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

    # Patch DB health check to avoid real DB connections
    import app.database.connection as db_conn

    async def _always_true():
        return True

    db_conn.check_database_connection = _always_true

    # app.main imported the function at module import time; patch that name too
    main.check_database_connection = _always_true
    # Ensure the app state has a checkpointer so /health reports connected
    try:
        main.app.state.langgraph_checkpointer = object()
    except Exception:
        # If app state isn't available yet, ignore — lifespan will set it.
        pass

    return main


def test_root_and_health_endpoints(monkeypatch):
    """Basic e2e checks for `/` and `/health`.

    These tests run the FastAPI TestClient but patch heavy dependencies
    (embedding preload, langgraph checkpointer, database health check)
    so they are deterministic and safe in CI.
    """

    main = _patch_app_for_tests(monkeypatch)

    client = TestClient(main.app)

    r = client.get("/")
    assert r.status_code == 200
    body = r.json()
    assert "Enterprise Support" in body.get("message", "")

    h = client.get("/health")
    assert h.status_code == 200
    hb = h.json()
    # Application should report ok because we patched health checks
    assert hb.get("status") == "ok"
    assert hb.get("database") == "connected"
    assert hb.get("langgraph_checkpointer") == "connected"
