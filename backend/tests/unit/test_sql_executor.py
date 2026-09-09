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

    async def execute(self, *args, **kwargs):
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
