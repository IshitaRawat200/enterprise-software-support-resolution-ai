from __future__ import annotations

import re
from typing import ClassVar


class SQLValidationError(ValueError):
    pass


class SQLValidator:
    """
    Validates generated SQL before execution.

    Security model:

        LLM
         ↓
        SQL
         ↓
        Validator
         ↓
        Read-only SELECT
         ↓
        Database
    """

    ALLOWED_TABLES: ClassVar[set[str]] = {
        "users",
        "customers",
        "subscriptions",
        "support_tickets",
        "ticket_messages",
        "conversation_history",
        "incident_logs",
        "knowledge_articles",
        "documents",
        "document_chunks",
        "escalations",
        "memory_facts",
        "agent_state",
        "audit_events",
        "knowledge_article_usage",
    }

    FORBIDDEN_KEYWORDS: ClassVar[set[str]] = {
        "insert",
        "update",
        "delete",
        "drop",
        "alter",
        "create",
        "truncate",
        "grant",
        "revoke",
        "execute",
        "call",
        "merge",
        "copy",
        "vacuum",
        "refresh",
    }

    def validate(
        self,
        sql: str,
    ) -> str:

        if not sql or not sql.strip():
            raise SQLValidationError("SQL query is empty.")

        normalized = sql.strip()

        # Remove trailing semicolon.
        normalized = normalized.rstrip(";").strip()

        lowered = normalized.lower()

        # ----------------------------------------------------
        # Must begin with SELECT or WITH
        # ----------------------------------------------------

        if not lowered.startswith(("select ", "select\n", "with ")):
            raise SQLValidationError("Only SELECT or WITH queries are allowed.")

        # ----------------------------------------------------
        # Multiple statements
        # ----------------------------------------------------

        if ";" in normalized:
            raise SQLValidationError("Multiple SQL statements are not allowed.")

        # ----------------------------------------------------
        # Forbidden operations
        # ----------------------------------------------------

        for keyword in self.FORBIDDEN_KEYWORDS:
            pattern = rf"\b{re.escape(keyword)}\b"

            if re.search(
                pattern,
                lowered,
            ):
                raise SQLValidationError(f"Forbidden SQL operation: {keyword}")

        # ----------------------------------------------------
        # System databases
        # ----------------------------------------------------

        if (
            "pg_catalog" in lowered
            or "information_schema" in lowered
            or "pg_" in lowered
        ):
            raise SQLValidationError("System catalog access is not allowed.")

        # ----------------------------------------------------
        # Extract table references
        # ----------------------------------------------------

        table_matches = re.findall(
            r"\b(?:from|join)\s+"
            r"(?:public\.)?"
            r"([a-zA-Z_][a-zA-Z0-9_]*)",
            lowered,
        )

        for table in table_matches:
            if table not in self.ALLOWED_TABLES:
                raise SQLValidationError(f"Table '{table}' is not allowed.")

        # ----------------------------------------------------
        # LIMIT
        # ----------------------------------------------------

        if (
            not re.search(
                r"\blimit\s+\d+\b",
                lowered,
            )
            and "count(" not in lowered
            and "sum(" not in lowered
            and "avg(" not in lowered
            and "min(" not in lowered
            and "max(" not in lowered
        ):
            normalized = normalized + "\nLIMIT 50"

        return normalized
