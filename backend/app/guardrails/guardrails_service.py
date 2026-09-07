from __future__ import annotations

from typing import Any

from app.guardrails.guardrail_result import GuardrailResult
from app.guardrails.handoff_guardrail import (
    evaluate_handoff_conditions,
)
from app.guardrails.input_guardrail import (
    validate_input,
)
from app.guardrails.output_guardrail import (
    sanitize_output_text,
    validate_output_text,
    validate_response_payload,
)
from app.guardrails.pii_guardrail import pii_guardrail
from app.guardrails.resource_guardrail import (
    can_access_customer,
)
from app.guardrails.security_guardrail import (
    inspect_message,
)
from app.guardrails.tool_guardrail import (
    validate_sql_query,
    validate_tool_call,
)

# =============================================================
# GUARDRAILS SERVICE
# =============================================================


class GuardrailsService:
    """
    Central orchestration service for application guardrails.

    This service does NOT execute RAG, SQL, MCP, or LangGraph.

    Instead, it validates and protects those operations.

    Responsibilities:

        INPUT
            ├── input validation
            └── prompt-injection/security validation

        TOOL
            ├── MCP authorization
            ├── MCP argument validation
            └── SQL safety validation

        RESOURCE
            └── customer/account authorization

        OUTPUT
            ├── response structure validation
            ├── secret leakage detection
            └── internal-content protection

        HANDOFF
            ├── critical severity
            ├── security incident
            ├── production incident
            ├── explicit human request
            ├── high severity
            └── low confidence/evaluation failure


    Architecture:

        POST /chat
             |
             v
        GuardrailsService
             |
             +--> validate_input()
             |
             +--> inspect_security()
             |
             v
          LangGraph
             |
             +--> RAG
             +--> SQL
             +--> Hybrid
             +--> MCP
             |
             v
        GuardrailsService
             |
             +--> validate_output()
             +--> validate_response()
             +--> evaluate_handoff()
             |
             v
        Customer / Human Support
    """

    def __init__(self) -> None:
        """
        Initialize the central guardrail service.

        The individual guardrails are deterministic functions,
        so no external model or database connection is required
        during initialization.
        """

        self.name = "guardrails_service"

    # =========================================================
    # INPUT GUARDRAILS
    # =========================================================

    def validate_customer_input(
        self,
        message: str,
    ) -> GuardrailResult:
        """
        Validate a customer message before LangGraph execution.

        Performs:
            - type validation
            - empty-message validation
            - length validation
            - control-character validation
            - excessive-repetition detection
            - prompt-injection detection
            - security-pattern detection
        """

        return validate_input(message)

    # =========================================================
    # SECURITY GUARDRAIL
    # =========================================================

    def inspect_security(
        self,
        message: str,
    ) -> GuardrailResult:
        """
        Inspect a message specifically for security threats.

        Detects:
            - prompt injection
            - system prompt extraction
            - chain-of-thought extraction
            - secret/credential extraction
            - authorization bypass attempts
        """

        return inspect_message(message)

    def inspect_pii(self, text: str) -> dict[str, Any]:
        """
        Detect PII in user-provided text.

        PII is detected deterministically and is not blocked by default.
        The caller can decide whether the text should be sanitized.
        """

        result = pii_guardrail.inspect(text)

        return {
            "contains_pii": result.contains_pii,
            "pii_types": result.pii_types,
            "match_count": len(result.matches),
        }

    # =========================================================
    # MCP / TOOL GUARDRAIL
    # =========================================================

    def validate_tool(
        self,
        *,
        tool_name: str,
        role: str,
        arguments: dict[str, Any] | None = None,
    ) -> GuardrailResult:
        """
        Validate an MCP/tool invocation before execution.

        The MCP permission map remains the source of truth
        for role-based MCP permissions.
        """

        return validate_tool_call(
            tool_name=tool_name,
            role=role,
            arguments=arguments,
        )

    # =========================================================
    # SQL GUARDRAIL
    # =========================================================

    def validate_sql(
        self,
        query: str,
    ) -> GuardrailResult:
        """
        Validate generated SQL before execution.

        This is an additional safety layer.

        The existing SQLService/SQL validator remains
        responsible for the application's complete SQL policy.
        """

        return validate_sql_query(query)

    # =========================================================
    # RESOURCE AUTHORIZATION
    # =========================================================

    def validate_customer_access(
        self,
        *,
        current_user: Any,
        customer_id: str | None,
    ) -> GuardrailResult:
        """
        Validate whether the authenticated user may access
        the requested customer's resources.

        This protects against cross-customer data access.
        """

        return can_access_customer(
            current_user=current_user,
            customer_id=customer_id,
        )

    def validate_ticket_access(
        self,
        *,
        current_user: Any,
        ticket_customer_id: str | None,
    ) -> GuardrailResult:
        """
        Validate whether the authenticated user may access
        a ticket belonging to a particular customer.
        """

        from app.guardrails.resource_guardrail import (
            can_access_ticket,
        )

        return can_access_ticket(
            current_user=current_user,
            ticket_customer_id=ticket_customer_id,
        )

    # =========================================================
    # OUTPUT GUARDRAIL
    # =========================================================

    def validate_output(
        self,
        answer: str,
    ) -> GuardrailResult:
        """
        Validate customer-facing answer text.

        Protects against:
            - secret leakage
            - credential leakage
            - JWT leakage
            - API-key leakage
            - private/internal instructions
            - chain-of-thought leakage
        """

        return validate_output_text(answer)

    def sanitize_pii(self, text: str) -> str:
        """
        Redact detected PII before text is passed to downstream
        AI components when redaction is appropriate.
        """

        return pii_guardrail.sanitize(text)

    def sanitize_output(
        self,
        answer: str,
    ) -> tuple[str, GuardrailResult]:
        """
        Sanitize an answer by redacting detected secrets.

        This is a defensive final layer.

        For strict security-sensitive cases, callers should
        prefer validate_output() and block the response.
        """

        return sanitize_output_text(answer)

    # =========================================================
    # RESPONSE CONTRACT
    # =========================================================

    def validate_response(
        self,
        response: dict[str, Any],
    ) -> GuardrailResult:
        """
        Validate the structured support response contract.

        Expected fields include:

            answer
            intent
            route
            severity
            confidence
            escalation_required
        """

        return validate_response_payload(response)

    # =========================================================
    # HANDOFF / ESCALATION GUARDRAIL
    # =========================================================

    def evaluate_handoff(
        self,
        *,
        message: str,
        severity: str | None,
        escalation_required: bool = False,
        faithfulness: float | None = None,
        relevance: float | None = None,
        confidence: float | None = None,
        no_chunks: bool = False,
        production_incident: bool = False,
        security_incident: bool = False,
    ) -> dict[str, Any]:
        """
        Apply deterministic escalation safety rules.

        Escalation can be triggered by:

            1. Critical severity
            2. Security incident
            3. Production incident
            4. Explicit human request
            5. High severity
            6. Low confidence
            7. Poor answer quality
            8. Existing Escalation Manager decision
        """

        return evaluate_handoff_conditions(
            message=message,
            severity=severity,
            escalation_required=escalation_required,
            faithfulness=faithfulness,
            relevance=relevance,
            confidence=confidence,
            no_chunks=no_chunks,
            production_incident=production_incident,
            security_incident=security_incident,
        )

    # =========================================================
    # FULL INPUT PIPELINE
    # =========================================================

    def validate_request(
        self,
        message: str,
    ) -> GuardrailResult:
        """
        Run the complete input security pipeline.

        Order:

            Input validation
                ↓
            Security inspection

        This method is intended to run before LangGraph.
        """

        input_result = self.validate_customer_input(
            message
        )

        if not input_result.allowed:
            return input_result

        security_result = self.inspect_security(
            message
        )

        if not security_result.allowed:
            return security_result

        pii_result = self.inspect_pii(message)

        sanitized_message = self.sanitize_pii(message)
        return GuardrailResult.allow(
            self.name,
            reason="Request passed all input guardrails.",
            metadata={
                "input_guardrail": "passed",
                "security_guardrail": "passed",
                "pii_detection": pii_result,
                "pii_detected": pii_result["contains_pii"],
                "pii_types": pii_result["pii_types"],
                "sanitized_message": sanitized_message,
            },
        )

    # =========================================================
    # FULL OUTPUT PIPELINE
    # =========================================================

    def validate_final_response(
        self,
        response: dict[str, Any],
    ) -> GuardrailResult:
        """
        Run the complete output validation pipeline.

        Order:

            Response schema
                ↓
            Customer-facing answer validation

        This method should run immediately before returning
        the response to the customer.
        """

        response_result = self.validate_response(
            response
        )

        if not response_result.allowed:
            return response_result

        answer = response.get("answer")

        output_result = self.validate_output(
            answer
        )

        if not output_result.allowed:
            return output_result

        return GuardrailResult.allow(
            self.name,
            reason="Response passed all output guardrails.",
            metadata={
                "response_schema": "passed",
                "output_security": "passed",
            },
        )

    # =========================================================
    # FULL TOOL PIPELINE
    # =========================================================

    def validate_mcp_call(
        self,
        *,
        tool_name: str,
        role: str,
        arguments: dict[str, Any] | None = None,
    ) -> GuardrailResult:
        """
        Validate an MCP call before it reaches MCPService.
        """

        return self.validate_tool(
            tool_name=tool_name,
            role=role,
            arguments=arguments,
        )

    # =========================================================
    # GUARDRAIL SUMMARY
    # =========================================================

    def get_capabilities(self) -> dict[str, Any]:
        """
        Return a description of enabled guardrail capabilities.

        This is useful for health/debug endpoints and
        observability. It does not expose internal prompts,
        secrets, or private reasoning.
        """

        return {
            "service": self.name,
            "input_validation": True,
            "prompt_injection_detection": True,
            "security_inspection": True,
            "pii_detection": True,
            "pii_redaction": True,
            "mcp_tool_authorization": True,
            "sql_safety_validation": True,
            "customer_resource_authorization": True,
            "output_validation": True,
            "secret_leakage_detection": True,
            "internal_content_protection": True,
            "response_contract_validation": True,
            "handoff_escalation_guardrail": True,
        }


# =============================================================
# SHARED SERVICE INSTANCE
# =============================================================

guardrails_service = GuardrailsService()