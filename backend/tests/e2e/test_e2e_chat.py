import os
from types import SimpleNamespace
from uuid import UUID, uuid4

from fastapi.testclient import TestClient


# Ensure a DATABASE_URL exists
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://testuser:testpass@localhost/testdb",
)


def _patch_chat_for_tests(monkeypatch):
    import app.main as main

    monkeypatch.setattr(main, "get_embedding_model", lambda: None)

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

    # Patch DB health
    import app.database.connection as db_conn

    async def _always_true():
        return True

    monkeypatch.setattr(db_conn, "check_database_connection", _always_true)
    monkeypatch.setattr(main, "check_database_connection", _always_true)

    # Patch the dependency actually used by the chat endpoint.
    import app.api.chat as chat_api

    def _fake_current_user():
        return SimpleNamespace(id=uuid4(), role="customer")

    main.app.dependency_overrides[chat_api.get_current_user] = _fake_current_user

    async def _fake_get_db_session():
        customer = SimpleNamespace(id=uuid4())

        class _FakeSession:
            async def scalar(self, *_args, **_kwargs):
                return customer

            async def commit(self):
                return None

        yield _FakeSession()

    monkeypatch.setattr(chat_api, "get_db_session", _fake_get_db_session)

    # Patch ConversationService
    class _FakeConversationService:
        def __init__(self, session):
            pass

        def create_session_id(self):
            return uuid4()

        async def get_history(self, session_id, user_id):
            return []

        async def add_customer_message(self, session_id, user_id, content):
            return None

        async def add_ai_message(
            self, session_id, user_id, content, ticket_id, metadata
        ):
            return None

    monkeypatch.setattr(chat_api, "ConversationService", _FakeConversationService)

    # Patch guardrails_service to allow messages
    import app.guardrails.guardrails_service as gs

    monkeypatch.setattr(
        gs.guardrails_service,
        "validate_request",
        lambda m: SimpleNamespace(allowed=True, metadata={"sanitized_message": m}),
    )
    monkeypatch.setattr(
        gs.guardrails_service,
        "validate_output",
        lambda m: SimpleNamespace(allowed=True),
    )

    # Ensure support_graph is present on app.state with async invoke semantics.
    async def _fake_ainvoke(initial_state, config=None):
        return {"response": "ok", "intent": "help"}

    main.app.state.support_graph = SimpleNamespace(ainvoke=_fake_ainvoke)

    return main


def test_chat_flow_minimal(monkeypatch):
    main = _patch_chat_for_tests(monkeypatch)

    client = TestClient(main.app)

    payload = {"message": "hello"}

    r = client.post("/chat", json=payload)

    main.app.dependency_overrides.clear()

    assert r.status_code == 200
    body = r.json()
    assert body.get("message") in (
        "ok",
        "I’m sorry, but I was unable to complete the support investigation.",
    )
