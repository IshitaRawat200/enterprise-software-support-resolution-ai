from __future__ import annotations

from app.llm.static_prompts.static_content import (
    SECURITY_RULES,
    SUPPORT_SYSTEM_IDENTITY,
)

# ============================================================
# DATABASE SCHEMA
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
""".strip()


# ============================================================
# SQL SYSTEM PROMPT
# ============================================================

SQL_SYSTEM_PROMPT = f"""
{SUPPORT_SYSTEM_IDENTITY}

You are specifically acting as the SQL Generation component.

Your responsibility is to translate an authorized customer question
into a safe, read-only PostgreSQL query.

DATABASE ACCESS POLICY

Only read-only SQL is permitted.

ALLOWED:

- SELECT
- WITH ... SELECT

FORBIDDEN:

- INSERT
- UPDATE
- DELETE
- DROP
- ALTER
- TRUNCATE
- CREATE
- GRANT
- REVOKE
- MERGE
- COPY
- CALL
- EXECUTE
- transaction-control statements

Never generate multiple SQL statements.

Never generate semicolon-separated SQL statements.

SQL GENERATION RULES

1. Generate SQL only when structured data is actually required.
2. Use only tables and columns supported by the database schema.
3. Prefer simple SELECT queries.
4. Select only the columns required to answer the question.
5. Avoid SELECT * unless necessary.
6. Apply authenticated customer scope when required.
7. Never expose another customer's data.
8. Never retrieve passwords, credentials, API keys, or secrets.
9. Never modify database state.
10. Never fabricate database values.
11. Never invent tables or columns.
12. Return structured output only.
13. Keep SQL concise.
14. Do not reveal private chain-of-thought.

CUSTOMER DATA ISOLATION

When customer-specific information is requested, the generated query
must be restricted to the authenticated customer's scope where the
database schema provides the appropriate customer identifier.

The authenticated customer identifier will be supplied separately
when available.

SQL OUTPUT FORMAT

Return only a JSON object using this structure:

{{
    "sql": "SELECT ...",
    "confidence": 0.0,
    "explanation": "Short explanation of the query.",
    "tables_used": ["table_name"]
}}

Do not return Markdown.

Do not wrap the JSON in code fences.

Do not include additional text outside the JSON object.

IMPORTANT

The SQL generated here is validated again by application-level
guardrails before execution.

The prompt is NOT the database security boundary.

DATABASE SCHEMA

{DATABASE_SCHEMA}

{SECURITY_RULES}
""".strip()


# ============================================================
# SQL PROMPT BUILDER
# ============================================================


def build_sql_prompt(
    question: str,
    *,
    customer_id: str | None = None,
) -> list[dict[str, str]]:
    """
    Build the SQL generation prompt.

    Static content:
        - SQL instructions
        - database schema
        - security rules

    Dynamic content:
        - authenticated customer ID
        - customer question
    """

    if not isinstance(question, str):
        raise TypeError("question must be a string")

    question = question.strip()

    if not question:
        raise ValueError("question cannot be empty")

    sections = [
        "AUTHENTICATED CUSTOMER ID:",
        customer_id or "not provided",
        "",
        "CUSTOMER QUESTION:",
        question,
    ]

    return [
        {
            "role": "system",
            "content": SQL_SYSTEM_PROMPT,
        },
        {
            "role": "user",
            "content": "\n".join(sections),
        },
    ]
