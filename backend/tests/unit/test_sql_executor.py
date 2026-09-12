from types import SimpleNamespace

from sqlalchemy.exc import SQLAlchemyError

from app.sql.sql_executor import SQLExecutor


class FakeResult:
    def __init__(self, rows):
        self._rows = rows

    def mappings(self):
        return SimpleNamespace(all=lambda: self._rows)


class FakeSession:
    def __init__(self, result=None, raise_exc=None):
        self._result = result
        self._raise = raise_exc
        self.calls = []

    async def execute(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        if self._raise:
            raise self._raise
        return self._result


def test_execute_success_returns_rows():
    import asyncio

    rows = [{"id": 1, "name": "alice"}]
    fake_result = FakeResult(rows)
    session = FakeSession(result=fake_result)

    executor = SQLExecutor(session=session)

    out = asyncio.run(executor.execute("SELECT id FROM users"))

    assert out["success"] is True
    assert out["row_count"] == 1
    assert out["rows"][0]["name"] == "alice"


def test_execute_handles_sqlalchemy_error():
    import asyncio

    session = FakeSession(raise_exc=SQLAlchemyError("boom"))

    executor = SQLExecutor(session=session)

    out = asyncio.run(executor.execute("SELECT id FROM users"))

    assert out["success"] is False
    assert out.get("error")


def test_execute_binds_positional_parameter():
    import asyncio

    rows = [{"id": "cust-1", "account_status": "active"}]
    session = FakeSession(result=FakeResult(rows))
    executor = SQLExecutor(session=session)

    out = asyncio.run(
        executor.execute(
            "SELECT account_status FROM customers WHERE id = $1 LIMIT 50",
            parameters=["cust-1"],
        )
    )

    assert out["success"] is True
    assert len(session.calls) == 1

    args, _kwargs = session.calls[0]
    compiled_sql = str(args[0])
    bound_params = args[1]

    assert ":p1" in compiled_sql
    assert bound_params == {"p1": "cust-1"}


def test_execute_rejects_missing_positional_parameter_without_execution():
    import asyncio

    session = FakeSession(result=FakeResult([]))
    executor = SQLExecutor(session=session)

    out = asyncio.run(
        executor.execute("SELECT account_status FROM customers WHERE id = $1 LIMIT 50")
    )

    assert out["success"] is False
    assert "expects 1 parameter" in (out["error"] or "")
    assert len(session.calls) == 0
