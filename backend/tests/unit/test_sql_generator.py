import asyncio
import json
from types import SimpleNamespace

import pytest

from app.sql import sql_generator as sg


@pytest.mark.parametrize(
    "bad_sql",
    [
        "",
        "INSERT INTO tbl VALUES (1)",
        "UPDATE tbl SET x=1",
        "DELETE FROM tbl",
        "DROP TABLE t",
        "SELECT 1; SELECT 2",
        "SELECT 1 AS answer",
    ],
)
def test_validate_generated_sql_rejects(bad_sql):
    if bad_sql == "":
        with pytest.raises(ValueError):
            sg.validate_generated_sql(bad_sql)
    else:
        with pytest.raises(ValueError):
            sg.validate_generated_sql(bad_sql)


def test_validate_generated_sql_accepts_and_fence():
    s = "```sql\nSELECT id FROM users WHERE active=1\n```"
    out = sg.validate_generated_sql(s)
    assert "select" in out.lower()


def test_extract_json_variants():
    # plain JSON
    d = {"sql": "SELECT 1"}
    assert sg._extract_json(json.dumps(d)) == d

    # fenced json
    fenced = "```json\n" + json.dumps(d) + "\n```"
    assert sg._extract_json(fenced) == d

    # surrounding text
    wrapped = 'Here is the result: {"sql": "SELECT 1"} thank you'
    assert sg._extract_json(wrapped) == d

    # malformed
    with pytest.raises(ValueError):
        sg._extract_json("no json here")


def test_sqlgenerator_success(monkeypatch):
    async def fake_ainvoke(prompt):
        return SimpleNamespace(
            content=json.dumps(
                {
                    "sql": "SELECT 1",
                    "confidence": 0.5,
                    "explanation": "ok",
                    "tables_used": ["users"],
                }
            )
        )

    # patch dependencies in module
    monkeypatch.setattr(sg, "assess_complexity", lambda q: "simple")
    monkeypatch.setattr(sg, "build_sql_prompt", lambda **kwargs: "PROMPT")

    class FakeLLM:
        async def ainvoke(self, prompt):
            return SimpleNamespace(
                content=json.dumps(
                    {
                        "sql": "SELECT 1",
                        "confidence": 0.5,
                        "explanation": "ok",
                        "tables_used": ["users"],
                    }
                )
            )

    monkeypatch.setattr(sg, "get_llm", lambda complexity: FakeLLM())

    gen = sg.SQLGenerator()
    result = asyncio.run(gen.generate("how many users?", customer_id=None))
    assert result.sql.strip().lower().startswith("select")


def test_sqlgenerator_missing_sql(monkeypatch):
    class FakeLLM:
        async def ainvoke(self, prompt):
            return SimpleNamespace(content=json.dumps({"no_sql": 1}))

    monkeypatch.setattr(sg, "assess_complexity", lambda q: "simple")
    monkeypatch.setattr(sg, "build_sql_prompt", lambda **kwargs: "PROMPT")
    monkeypatch.setattr(sg, "get_llm", lambda complexity: FakeLLM())

    gen = sg.SQLGenerator()
    with pytest.raises(ValueError):
        asyncio.run(gen.generate("q"))
