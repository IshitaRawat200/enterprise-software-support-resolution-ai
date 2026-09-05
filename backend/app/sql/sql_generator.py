from __future__ import annotations

import json
import re

from app.llm.complexity import assess_complexity
from app.llm.gateway import get_llm
from app.sql.sql_schema import SQLGenerationResult


# ============================================================
# ALLOWED DATABASE SCHEMA
# ============================================================

DATABASE_SCHEMA = """
PostgreSQL database schema.

Allowed tables:

users

customers

subscriptions

support_tickets

ticket_messages

conversation_history

incident_logs

knowledge_articles

documents

document_chunks

escalations

memory_facts

agent_state

audit_events

knowledge_article_usage

Important columns:

users:
    id
    email
    role
    is_active
    created_at
    updated_at

customers:
    id
    user_id
    customer_code
    contact_name
    company_name
    region
    industry
    account_status

subscriptions:
    id
    customer_id
    plan_name
    status
    start_date
    end_date
    created_at
    updated_at

support_tickets:
    id
    customer_id
    ticket_number
    status
    intent
    route
    severity
    confidence
    escalation_required
    escalation_reason
    ai_investigation_summary
    created_at
    updated_at

ticket_messages:
    id
    ticket_id
    sender_user_id
    sender_type
    message
    created_at

incident_logs:
    id
    ticket_id
    incident_type
    status
    severity
    description
    started_at
    resolved_at
    created_at

knowledge_articles:
    id
    article_code
    title
    description
    product_name
    product_version
    source_url
    version
    published_at
    is_active
    created_at
    updated_at

documents:
    id
    knowledge_article_id
    document_name
    document_type
    source_url
    product_name
    product_version
    version
    content_hash
    metadata
    created_at

document_chunks:
    id
    document_id
    chunk_index
    content
    token_count
    embedding
    metadata
    created_at

escalations:
    id
    ticket_id
    assigned_to_user_id
    reason
    status
    created_at
    updated_at
"""


# ============================================================
# SQL VALIDATION
# ============================================================


def validate_generated_sql(sql: str) -> str:
    """
    Validate and normalize LLM-generated SQL before execution.

    The SQL layer is read-only and must not contain
    natural-language troubleshooting responses.
    """

    sql = sql.strip()

    # Remove accidental Markdown fences.
    if sql.startswith("```"):
        sql = sql.replace("```sql", "", 1)
        sql = sql.replace("```", "")
        sql = sql.strip()

    if not sql:
        raise ValueError(
            "SQL generator returned an empty query."
        )

    normalized = sql.lower()

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
                "Unsafe SQL detected: "
                f"forbidden operation '{keyword.strip()}'."
            )

    if not normalized.startswith("select"):
        raise ValueError(
            "Only SELECT queries are allowed."
        )

    # Prevent the LLM from embedding support answers in SQL.
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
                "SQL query contains natural-language response content. "
                "Troubleshooting must be handled by RAG."
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

    content = content.strip()

    # Remove markdown code fences.
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

    try:
        return json.loads(content)

    except json.JSONDecodeError:
        # Look for the first JSON object.
        match = re.search(
            r"\{.*\}",
            content,
            flags=re.DOTALL,
        )

        if not match:
            raise ValueError(
                "LLM did not return valid JSON."
            )

        try:
            return json.loads(
                match.group(0)
            )

        except json.JSONDecodeError as exc:
            raise ValueError(
                "LLM returned malformed JSON."
            ) from exc


# ============================================================
# SQL GENERATOR
# ============================================================


class SQLGenerator:
    """
    Natural-language to SQL generator.

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

        if not question or not question.strip():
            raise ValueError(
                "SQL question cannot be empty."
            )

        question = question.strip()

        customer_context = (
            customer_id
            if customer_id
            else "not provided"
        )

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
        # PROMPT
        # ====================================================

        prompt = f"""
You are the SQL generation component of an enterprise
software support system.

Your ONLY responsibility is to generate a safe,
read-only PostgreSQL query for structured information
stored in the database.

IMPORTANT SEPARATION OF RESPONSIBILITIES:

- SQL is ONLY for structured database facts.

- Documentation, troubleshooting instructions,
  explanations, and general support advice are handled
  by the RAG system.

- NEVER put troubleshooting advice, explanations,
  recommendations, or natural-language answers inside
  a SQL query.

For example, DO NOT generate:

SELECT
    'Check the endpoint URL and API version' AS troubleshooting,
    account_status
FROM customers
...

Instead, generate SQL only for the structured
database information:

SELECT id, account_status
FROM customers
WHERE id = '...'
LIMIT 1

SQL RULES:

1. Generate exactly ONE PostgreSQL SELECT query.

2. Only generate SELECT statements.

3. Never generate:

   INSERT
   UPDATE
   DELETE
   DROP
   ALTER
   CREATE
   TRUNCATE
   GRANT
   REVOKE
   EXECUTE
   CALL
   MERGE

4. Only use tables and columns explicitly listed
   in the allowed schema.

5. Never access:

   pg_catalog

   information_schema

   system catalogs

   database metadata outside the provided schema.

6. Never modify database data.

7. Prefer explicit columns instead of SELECT *.

8. Add LIMIT 50 unless the query is an aggregate
   or already has a stricter LIMIT.

9. If customer-specific information is requested and
   customer_id is provided, constrain the query
   to that customer.

10. Do not invent tables or columns.

11. Do not answer documentation or troubleshooting
    questions using SQL.

12. If the user's request contains both a
    documentation/troubleshooting question and a
    structured-data question, generate SQL ONLY
    for the structured-data portion.

13. Never create artificial/natural-language columns
    such as:

    troubleshooting
    answer
    explanation
    advice
    recommendation
    response

14. The "explanation" field belongs to the JSON response
    and must NEVER be embedded inside the SQL query.

15. Return JSON only using exactly this structure:

{{
  "sql": "SELECT ...",
  "explanation": "Why this query answers the structured database portion.",
  "tables_used": ["customers"],
  "confidence": 0.95
}}

ALLOWED DATABASE SCHEMA:

{DATABASE_SCHEMA}

Authenticated customer_id:

{customer_context}

Customer question:

{question}

Remember:

Generate SQL ONLY for structured database information.

RAG handles documentation and troubleshooting.

Return JSON only.
"""

        # ====================================================
        # LLM GATEWAY
        # ====================================================

        llm = get_llm(
            complexity=complexity,
        )

        response = await llm.ainvoke(
            prompt
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
                item.get("text", str(item))
                if isinstance(item, dict)
                else str(item)
                for item in content
            )

        # ====================================================
        # JSON PARSING
        # ====================================================

        data = _extract_json(
            str(content)
        )

        # ====================================================
        # SQL VALIDATION
        # ====================================================

        if "sql" not in data:
            raise ValueError(
                "SQL generator response does not contain 'sql'."
            )

        data["sql"] = validate_generated_sql(
            data["sql"]
        )

        # ====================================================
        # FINAL SCHEMA VALIDATION
        # ====================================================

        return SQLGenerationResult.model_validate(
            data
        )