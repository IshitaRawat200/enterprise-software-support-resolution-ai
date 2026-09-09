from __future__ import annotations

import json
import re

from app.llm.complexity import assess_complexity
from app.llm.gateway import get_llm
from app.llm.static_prompts.sql_prompt import (
    build_sql_prompt,
)
from app.sql.sql_schema import SQLGenerationResult

# ============================================================
# SQL VALIDATION
# ============================================================


def validate_generated_sql(sql: str) -> str:
    """
    Validate and normalize LLM-generated SQL before execution.

    The SQL layer is read-only and must not contain
    natural-language troubleshooting responses.
    """

    if not isinstance(sql, str):
        raise TypeError("Generated SQL must be a string.")

    sql = sql.strip()

    # --------------------------------------------------------
    # Remove accidental Markdown fences.
    # --------------------------------------------------------

    if sql.startswith("```"):
        sql = sql.replace(
            "```sql",
            "",
            1,
        )
        sql = sql.replace(
            "```",
            "",
        )
        sql = sql.strip()

    if not sql:
        raise ValueError("SQL generator returned an empty query.")

    normalized = sql.lower()

    # --------------------------------------------------------
    # Block multiple statements.
    # --------------------------------------------------------

    statements = [
        statement.strip() for statement in sql.split(";") if statement.strip()
    ]

    if len(statements) > 1:
        raise ValueError("Multiple SQL statements are not allowed.")

    # --------------------------------------------------------
    # Forbidden operations.
    # --------------------------------------------------------

    forbidden_keywords = [
        "insert ",
        "update ",
        "delete ",
        "drop ",
        "alter ",
        "create ",
        "truncate ",
        "grant ",
        "revoke ",
        "execute ",
        "call ",
        "merge ",
    ]

    for keyword in forbidden_keywords:
        if keyword in normalized:
            raise ValueError(
                f"Unsafe SQL detected: forbidden operation '{keyword.strip()}'."
            )

    # --------------------------------------------------------
    # Only SELECT queries are allowed.
    # --------------------------------------------------------

    if not normalized.startswith("select"):
        raise ValueError("Only SELECT queries are allowed.")

    # --------------------------------------------------------
    # Prevent natural-language answers inside SQL.
    # --------------------------------------------------------

    suspicious_aliases = [
        " as troubleshooting",
        " as answer",
        " as explanation",
        " as response",
        " as advice",
        " as recommendation",
    ]

    for alias in suspicious_aliases:
        if alias in normalized:
            raise ValueError(
                "SQL query contains natural-language "
                "response content. Troubleshooting must "
                "be handled by RAG."
            )

    return sql


# ============================================================
# JSON EXTRACTION
# ============================================================


def _extract_json(content: str) -> dict:
    """
    Extract JSON from an LLM response.

    Handles:
    - plain JSON
    - ```json ... ```
    - accidental surrounding text containing a JSON object
    """

    if not isinstance(content, str):
        raise TypeError("LLM response content must be a string.")

    content = content.strip()

    # --------------------------------------------------------
    # Remove Markdown code fences.
    # --------------------------------------------------------

    content = re.sub(
        r"^```(?:json)?\s*",
        "",
        content,
        flags=re.IGNORECASE,
    )

    content = re.sub(
        r"\s*```$",
        "",
        content,
    )

    content = content.strip()

    # --------------------------------------------------------
    # Try direct JSON parsing first.
    # --------------------------------------------------------

    try:
        return json.loads(content)

    except json.JSONDecodeError:
        pass

    # --------------------------------------------------------
    # Look for the first JSON object.
    # --------------------------------------------------------

    match = re.search(
        r"\{.*\}",
        content,
        flags=re.DOTALL,
    )

    if not match:
        raise ValueError("LLM did not return valid JSON.")

    try:
        return json.loads(match.group(0))

    except json.JSONDecodeError as exc:
        raise ValueError("LLM returned malformed JSON.") from exc


# ============================================================
# SQL GENERATOR
# ============================================================


class SQLGenerator:
    """
    Natural-language to SQL generator.

    Responsibilities:

    1. Assess query complexity.
    2. Select the appropriate LLM through the gateway.
    3. Build the SQL prompt from centralized prompt definitions.
    4. Generate structured SQL JSON.
    5. Validate generated SQL.
    6. Return a validated SQLGenerationResult.

    The LLM generates SQL only.

    It does not execute SQL.

    Complexity is determined by the deterministic
    complexity evaluator.

    Model selection is handled by the LLM Gateway.
    """

    async def generate(
        self,
        question: str,
        customer_id: str | None = None,
    ) -> SQLGenerationResult:

        # ====================================================
        # INPUT VALIDATION
        # ====================================================

        if not question or not question.strip():
            raise ValueError("SQL question cannot be empty.")

        question = question.strip()

        # ====================================================
        # CUSTOMER CONTEXT
        # ====================================================

        customer_context = customer_id if customer_id else "not provided"

        # ====================================================
        # COMPLEXITY EVALUATION
        # ====================================================

        complexity = assess_complexity(
            question,
        )

        print("\n===== SQL GENERATOR =====")
        print(f"Question: {question}")
        print(f"Complexity: {complexity}")
        print("=========================\n")

        # ====================================================
        # CENTRALIZED PROMPT
        # ====================================================

        prompt = build_sql_prompt(
            question=question,
            customer_id=customer_context,
        )

        # ====================================================
        # LLM GATEWAY
        # ====================================================

        llm = get_llm(
            complexity=complexity,
        )

        response = await llm.ainvoke(
            prompt,
        )

        # ====================================================
        # RESPONSE CONTENT
        # ====================================================

        content = (
            response.content
            if hasattr(
                response,
                "content",
            )
            else str(response)
        )

        if isinstance(content, list):
            content = "".join(
                item.get(
                    "text",
                    str(item),
                )
                if isinstance(item, dict)
                else str(item)
                for item in content
            )

        # ====================================================
        # JSON PARSING
        # ====================================================

        data = _extract_json(
            str(content),
        )

        # ====================================================
        # RESPONSE VALIDATION
        # ====================================================

        if "sql" not in data:
            raise ValueError("SQL generator response does not contain 'sql'.")

        # ====================================================
        # SQL VALIDATION
        # ====================================================

        data["sql"] = validate_generated_sql(
            data["sql"],
        )

        # ====================================================
        # FINAL SCHEMA VALIDATION
        # ====================================================

        return SQLGenerationResult.model_validate(
            data,
        )
