from __future__ import annotations

import json
import re

from langchain_groq import ChatGroq

from app.config import get_settings
from app.sql.sql_schema import (
    SQLGenerationResult,
)


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
# LLM
# ============================================================


def create_sql_llm() -> ChatGroq:
    settings = get_settings()

    if not settings.groq_api_key:
        raise RuntimeError(
            "GROQ_API_KEY is not configured."
        )

    return ChatGroq(
        model=settings.groq_complex_model,
        api_key=settings.groq_api_key,
        temperature=0.0,
    )


# ============================================================
# JSON EXTRACTION
# ============================================================


def _extract_json(
    content: str,
) -> dict:

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

    try:

        return json.loads(content)

    except json.JSONDecodeError:

        match = re.search(
            r"\{.*\}",
            content,
            flags=re.DOTALL,
        )

        if not match:
            raise ValueError(
                "LLM did not return valid JSON."
            )

        return json.loads(
            match.group(0)
        )


# ============================================================
# GENERATOR
# ============================================================


class SQLGenerator:
    """
    Natural-language to SQL generator.

    The LLM generates SQL only.
    It does not execute SQL.
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

        customer_context = (
            customer_id
            if customer_id
            else "not provided"
        )

        prompt = f"""
You are the SQL generation component of an
enterprise software support system.

Generate ONE safe PostgreSQL SELECT query.

You MUST follow these rules:

1. Only generate SELECT statements.
2. Never generate INSERT, UPDATE, DELETE, DROP,
   ALTER, CREATE, TRUNCATE, GRANT, REVOKE,
   EXECUTE, or CALL.
3. Only use the allowed tables and columns.
4. Never access system catalogs.
5. Never access pg_catalog.
6. Never access information_schema.
7. Never modify database data.
8. Prefer explicit columns instead of SELECT *.
9. Add LIMIT 50 unless the query is an aggregate.
10. If customer-specific data is requested and a
    customer_id is provided, constrain the query
    to that customer.
11. Do not invent columns.
12. Return JSON only.

{DATABASE_SCHEMA}

Authenticated customer_id:
{customer_context}

Customer question:

{question}

Return exactly this JSON structure:

{{
  "sql": "SELECT ...",
  "explanation": "Why this query answers the question.",
  "tables_used": ["customers"],
  "confidence": 0.95
}}
"""

        llm = create_sql_llm()

        response = await llm.ainvoke(
            prompt
        )

        content = (
            response.content
            if hasattr(
                response,
                "content",
            )
            else str(response)
        )

        data = _extract_json(
            content
        )

        return SQLGenerationResult.model_validate(
            data
        )