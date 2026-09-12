import asyncio
from types import SimpleNamespace

from app.sql.sql_service import SQLService


def test_sql_service_passes_customer_id_for_dollar_placeholder(monkeypatch):
    class FakeGeneration:
        sql = "SELECT account_status, subscription_tier FROM customers WHERE id = $1 LIMIT 50"
        confidence = 0.93
        explanation = "Look up account fields for authenticated customer."
        tables_used = ["customers"]
        parameters = None

    async def fake_generate(self, question, customer_id=None):
        return FakeGeneration()

    captured = {}

    async def fake_execute(self, sql, parameters=None):
        captured["sql"] = sql
        captured["parameters"] = parameters
        return {
            "success": True,
            "sql": sql,
            "rows": [{"account_status": "active", "subscription_tier": "enterprise"}],
            "row_count": 1,
            "error": None,
        }

    monkeypatch.setattr("app.sql.sql_generator.SQLGenerator.generate", fake_generate)
    monkeypatch.setattr(
        "app.guardrails.guardrails_service.guardrails_service.validate_sql",
        lambda sql: SimpleNamespace(
            allowed=True,
            reason="ok",
            guardrail_name="g",
            code="C",
            risk_level=1,
        ),
    )
    monkeypatch.setattr("app.sql.sql_executor.SQLExecutor.execute", fake_execute)

    svc = SQLService(session=SimpleNamespace())
    out = asyncio.run(
        svc.query(
            "What is my account status and subscription tier?",
            customer_id="auth-customer-id",
        )
    )

    assert out["success"] is True
    assert captured["sql"].startswith("SELECT account_status")
    assert captured["parameters"] == ["auth-customer-id"]


def test_sql_service_rejects_customer_scoped_query_without_customer_id(monkeypatch):
    class FakeGeneration:
        sql = "SELECT account_status FROM customers WHERE id = $1 LIMIT 50"
        confidence = 0.7
        explanation = "Account lookup"
        tables_used = ["customers"]
        parameters = None

    async def fake_generate(self, question, customer_id=None):
        return FakeGeneration()

    monkeypatch.setattr("app.sql.sql_generator.SQLGenerator.generate", fake_generate)

    svc = SQLService(session=SimpleNamespace())

    try:
        asyncio.run(svc.query("What is my account status?", customer_id=None))
        assert False, "Expected ValueError when customer_id is missing"
    except ValueError as exc:
        assert "customer_id is required" in str(exc)


def test_sql_service_overrides_generator_customer_param_with_authenticated_customer(monkeypatch):
    class FakeGeneration:
        sql = "SELECT account_status FROM customers WHERE id = $1 LIMIT 50"
        confidence = 0.8
        explanation = "Account lookup"
        tables_used = ["customers"]
        parameters = ["other-customer-id"]

    async def fake_generate(self, question, customer_id=None):
        return FakeGeneration()

    captured = {}

    async def fake_execute(self, sql, parameters=None):
        captured["parameters"] = parameters
        return {
            "success": True,
            "sql": sql,
            "rows": [{"account_status": "active"}],
            "row_count": 1,
            "error": None,
        }

    monkeypatch.setattr("app.sql.sql_generator.SQLGenerator.generate", fake_generate)
    monkeypatch.setattr(
        "app.guardrails.guardrails_service.guardrails_service.validate_sql",
        lambda sql: SimpleNamespace(
            allowed=True,
            reason="ok",
            guardrail_name="g",
            code="C",
            risk_level=1,
        ),
    )
    monkeypatch.setattr("app.sql.sql_executor.SQLExecutor.execute", fake_execute)

    svc = SQLService(session=SimpleNamespace())
    out = asyncio.run(svc.query("What is my account status?", customer_id="auth-customer-id"))

    assert out["success"] is True
    assert captured["parameters"] == ["auth-customer-id"]
