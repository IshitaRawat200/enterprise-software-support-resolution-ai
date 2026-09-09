from __future__ import annotations

import re
from typing import Any

from app.guardrails.guardrail_result import GuardrailResult
from app.mcp.mcp_permissions import MCP_TOOL_PERMISSIONS

GUARDRAIL_NAME = "tool_guardrail"


# ============================================================
# TOOL LIMITS
# ============================================================

ALLOWED_TOOL_NAMES = frozenset(MCP_TOOL_PERMISSIONS.keys())


# Explicit argument schema for every MCP tool.
#
# The guardrail rejects arguments that are not expected by
# the selected tool. This prevents callers from injecting
# arbitrary parameters into MCP tool calls.
TOOL_ARGUMENTS = {
    "mcp_validate_customer_account": frozenset(
        {
            "customer_id",
        }
    ),
    "mcp_check_incident_status": frozenset(
        {
            "service_name",
        }
    ),
    "mcp_get_support_policy": frozenset(
        {
            "policy_type",
        }
    ),
    "mcp_get_live_service_status": frozenset(
        {
            "service_name",
        }
    ),
}


MAX_ARGUMENT_STRING_LENGTH = 4_000
MAX_ARGUMENT_KEY_LENGTH = 200
MAX_ARGUMENT_DEPTH = 8
MAX_ARGUMENT_LIST_LENGTH = 100


# ============================================================
# SQL DANGEROUS PATTERNS
# ============================================================

DANGEROUS_SQL_PATTERNS: tuple[str, ...] = (
    r"\bdrop\s+table\b",
    r"\bdrop\s+database\b",
    r"\btruncate\s+table\b",
    r"\balter\s+table\b",
    r"\bcreate\s+table\b",
    r"\bcreate\s+database\b",
    r"\binsert\s+into\b",
    r"\bupdate\s+\w+\s+set\b",
    r"\bdelete\s+from\b",
    r"\bgrant\s+\w+\b",
    r"\brevoke\s+\w+\b",
    r"\bcopy\s+.+\s+to\b",
    r"\bpg_read_file\b",
    r"\bpg_write_file\b",
    r"\bpg_ls_dir\b",
)


def _contains_dangerous_sql(
    query: str,
) -> bool:
    """
    Return True when SQL contains a known dangerous operation.
    """

    normalized = query.strip().lower()

    for pattern in DANGEROUS_SQL_PATTERNS:
        if re.search(
            pattern,
            normalized,
            flags=re.IGNORECASE,
        ):
            return True

    return False


# ============================================================
# MCP ARGUMENT VALUE VALIDATION
# ============================================================


def _validate_argument_values(
    value: Any,
    *,
    depth: int = 0,
) -> tuple[bool, str | None]:
    """
    Validate MCP tool arguments recursively.

    Returns:
        (True, None) when the value is safe.
        (False, reason) when the value is unsafe.
    """

    # Prevent deeply nested structures from being used to
    # exhaust application resources.
    if depth > MAX_ARGUMENT_DEPTH:
        return (
            False,
            "Tool arguments are nested too deeply.",
        )

    # --------------------------------------------------------
    # Strings
    # --------------------------------------------------------

    if isinstance(value, str):
        if len(value) > MAX_ARGUMENT_STRING_LENGTH:
            return (
                False,
                (
                    "Tool argument string exceeds "
                    f"{MAX_ARGUMENT_STRING_LENGTH} characters."
                ),
            )

        return True, None

    # --------------------------------------------------------
    # Dictionaries
    # --------------------------------------------------------

    if isinstance(value, dict):
        for key, nested_value in value.items():
            if not isinstance(key, str):
                return (
                    False,
                    "Tool argument keys must be strings.",
                )

            if len(key) > MAX_ARGUMENT_KEY_LENGTH:
                return (
                    False,
                    "Tool argument key is too long.",
                )

            valid, reason = _validate_argument_values(
                nested_value,
                depth=depth + 1,
            )

            if not valid:
                return False, reason

        return True, None

    # --------------------------------------------------------
    # Lists / Tuples
    # --------------------------------------------------------

    if isinstance(value, (list, tuple)):
        if len(value) > MAX_ARGUMENT_LIST_LENGTH:
            return (
                False,
                "Tool argument list is too large.",
            )

        for item in value:
            valid, reason = _validate_argument_values(
                item,
                depth=depth + 1,
            )

            if not valid:
                return False, reason

        return True, None

    # --------------------------------------------------------
    # Primitive values
    # --------------------------------------------------------

    if value is None or isinstance(
        value,
        (bool, int, float),
    ):
        return True, None

    # --------------------------------------------------------
    # Unsupported types
    # --------------------------------------------------------

    return (
        False,
        (f"Unsupported tool argument type: {type(value).__name__}"),
    )


# ============================================================
# MCP TOOL CALL GUARDRAIL
# ============================================================


def validate_tool_call(
    *,
    tool_name: str,
    role: str,
    arguments: dict[str, Any] | None = None,
) -> GuardrailResult:
    """
    Validate an MCP tool call before execution.

    Checks:
        1. Tool is allow-listed.
        2. Role is authorized.
        3. Arguments are a dictionary.
        4. Arguments contain only approved fields.
        5. Argument values pass recursive safety validation.

    This function must execute before the MCP client sends
    the request to the MCP server.
    """

    # ========================================================
    # 1. TOOL NAME / ALLOW-LIST
    # ========================================================

    if not tool_name or not tool_name.strip():
        return GuardrailResult.block(
            GUARDRAIL_NAME,
            reason="MCP tool name is required.",
            code="TOOL_NAME_MISSING",
            risk_level="high",
            metadata={
                "tool_name": tool_name,
            },
        )

    if tool_name not in ALLOWED_TOOL_NAMES:
        return GuardrailResult.block(
            GUARDRAIL_NAME,
            reason=(f"MCP tool '{tool_name}' is not allow-listed."),
            code="TOOL_NOT_ALLOWED",
            risk_level="high",
            metadata={
                "tool_name": tool_name,
            },
        )

    # ========================================================
    # 2. ROLE AUTHORIZATION
    # ========================================================

    if not role or not role.strip():
        return GuardrailResult.block(
            GUARDRAIL_NAME,
            reason="MCP tool role is required.",
            code="ROLE_MISSING",
            risk_level="high",
            metadata={
                "tool_name": tool_name,
            },
        )

    allowed_roles = MCP_TOOL_PERMISSIONS.get(
        tool_name,
        frozenset(),
    )

    if role not in allowed_roles:
        return GuardrailResult.block(
            GUARDRAIL_NAME,
            reason=(f"Role '{role}' is not authorized to call MCP tool '{tool_name}'."),
            code="TOOL_ROLE_FORBIDDEN",
            risk_level="high",
            metadata={
                "tool_name": tool_name,
                "role": role,
                "allowed_roles": sorted(allowed_roles),
            },
        )

    # ========================================================
    # 3. ARGUMENT TYPE VALIDATION
    # ========================================================

    tool_arguments = arguments

    if tool_arguments is None:
        tool_arguments = {}

    if not isinstance(tool_arguments, dict):
        return GuardrailResult.block(
            GUARDRAIL_NAME,
            reason=("MCP tool arguments must be a dictionary."),
            code="INVALID_TOOL_ARGUMENTS",
            risk_level="high",
            metadata={
                "tool_name": tool_name,
                "argument_type": type(tool_arguments).__name__,
            },
        )

    # ========================================================
    # 4. ARGUMENT NAME VALIDATION
    # ========================================================

    allowed_arguments = TOOL_ARGUMENTS.get(
        tool_name,
        frozenset(),
    )

    unexpected_arguments = set(tool_arguments.keys()) - set(allowed_arguments)

    if unexpected_arguments:
        return GuardrailResult.block(
            GUARDRAIL_NAME,
            reason=(
                "MCP tool call contains unexpected "
                f"arguments: {sorted(unexpected_arguments)}."
            ),
            code="UNEXPECTED_TOOL_ARGUMENT",
            risk_level="high",
            metadata={
                "tool_name": tool_name,
                "unexpected_arguments": sorted(unexpected_arguments),
                "allowed_arguments": sorted(allowed_arguments),
            },
        )

    # ========================================================
    # 5. ARGUMENT VALUE VALIDATION
    # ========================================================

    for key, value in tool_arguments.items():
        valid, reason = _validate_argument_values(value)

        if not valid:
            return GuardrailResult.block(
                GUARDRAIL_NAME,
                reason=(f"Invalid value detected for MCP argument '{key}': {reason}"),
                code="INVALID_TOOL_ARGUMENTS",
                risk_level="high",
                metadata={
                    "tool_name": tool_name,
                    "argument": key,
                    "reason": reason,
                },
            )

    # ========================================================
    # ALLOW
    # ========================================================

    return GuardrailResult.allow(
        GUARDRAIL_NAME,
        reason=("MCP tool call passed all guardrail checks."),
        metadata={
            "tool_name": tool_name,
            "role": role,
            "validated_arguments": sorted(tool_arguments.keys()),
        },
    )


# ============================================================
# SQL GUARDRAIL
# ============================================================


def validate_sql_query(
    query: str,
) -> GuardrailResult:
    """
    Additional safety check for generated SQL.

    This is a guardrail only. The existing SQL validator/service
    remains responsible for the authoritative SQL policy.

    Allowed:
        - SELECT
        - WITH ... SELECT

    Blocked:
        - INSERT
        - UPDATE
        - DELETE
        - DROP
        - ALTER
        - TRUNCATE
        - CREATE
        - GRANT
        - REVOKE
        - COPY
        - PostgreSQL file-system functions
        - Multiple SQL statements
    """

    # ========================================================
    # 1. TYPE VALIDATION
    # ========================================================

    if not isinstance(query, str):
        return GuardrailResult.block(
            GUARDRAIL_NAME,
            reason="SQL query must be a string.",
            risk_level="high",
            code="INVALID_SQL_TYPE",
        )

    normalized = query.strip()

    # ========================================================
    # 2. EMPTY QUERY
    # ========================================================

    if not normalized:
        return GuardrailResult.block(
            GUARDRAIL_NAME,
            reason="SQL query cannot be empty.",
            risk_level="high",
            code="EMPTY_SQL",
        )

    # ========================================================
    # 3. MULTI-STATEMENT PROTECTION
    # ========================================================

    # A single trailing semicolon is harmless.
    # Any semicolon before the end means multiple statements.
    if ";" in normalized.rstrip(";"):
        return GuardrailResult.block(
            GUARDRAIL_NAME,
            reason=("Multiple SQL statements are not allowed."),
            risk_level="high",
            code="MULTI_STATEMENT_SQL",
        )

    # ========================================================
    # 4. DANGEROUS SQL OPERATIONS
    # ========================================================

    if _contains_dangerous_sql(normalized):
        return GuardrailResult.block(
            GUARDRAIL_NAME,
            reason=("Potentially unsafe SQL operation detected."),
            risk_level="high",
            code="DANGEROUS_SQL",
        )

    # ========================================================
    # 5. READ-ONLY STATEMENT CHECK
    # ========================================================

    if not re.match(
        r"^\s*(select|with)\b",
        normalized,
        flags=re.IGNORECASE,
    ):
        return GuardrailResult.block(
            GUARDRAIL_NAME,
            reason=("Only read-only SELECT/WITH SQL is permitted."),
            risk_level="high",
            code="NON_READ_ONLY_SQL",
        )

    # ========================================================
    # ALLOW
    # ========================================================

    return GuardrailResult.allow(
        GUARDRAIL_NAME,
        reason=("SQL passed the basic read-only safety guardrail."),
        metadata={
            "read_only": True,
            "statement_type": (
                "WITH"
                if re.match(
                    r"^\s*with\b",
                    normalized,
                    flags=re.IGNORECASE,
                )
                else "SELECT"
            ),
        },
    )
