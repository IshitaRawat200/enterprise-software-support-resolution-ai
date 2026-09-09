from app.guardrails.pii_guardrail import PIIGuardrail


def test_email_is_detected():
    guardrail = PIIGuardrail()

    result = guardrail.inspect("Please contact me at john.doe@example.com")

    assert result.contains_pii is True
    assert "email" in result.pii_types


def test_phone_number_is_detected():
    guardrail = PIIGuardrail()

    result = guardrail.inspect("Call me at +1 415-555-1234")

    assert result.contains_pii is True
    assert "phone" in result.pii_types


def test_ssn_is_detected():
    guardrail = PIIGuardrail()

    result = guardrail.inspect("My SSN is 123-45-6789")

    assert result.contains_pii is True
    assert "ssn" in result.pii_types


def test_credit_card_is_detected():
    guardrail = PIIGuardrail()

    result = guardrail.inspect("Card number: 4111 1111 1111 1111")

    assert result.contains_pii is True
    assert "credit_card" in result.pii_types


def test_ip_address_is_detected():
    guardrail = PIIGuardrail()

    result = guardrail.inspect("The client connected from 192.168.1.10")

    assert result.contains_pii is True
    assert "ip_address" in result.pii_types


def test_invalid_ip_is_not_detected():
    guardrail = PIIGuardrail()

    result = guardrail.inspect("Example value 999.999.999.999")

    assert "ip_address" not in result.pii_types


def test_normal_text_contains_no_pii():
    guardrail = PIIGuardrail()

    result = guardrail.inspect("The API returns HTTP 404 when the resource is missing.")

    assert result.contains_pii is False
    assert result.matches == []


def test_email_is_sanitized():
    guardrail = PIIGuardrail()

    result = guardrail.sanitize("Contact john.doe@example.com for assistance.")

    assert result == ("Contact [REDACTED_EMAIL] for assistance.")


def test_multiple_pii_values_are_sanitized():
    guardrail = PIIGuardrail()

    result = guardrail.sanitize("Email john@example.com or call +1 415-555-1234.")

    assert "[REDACTED_EMAIL]" in result
    assert "[REDACTED_PHONE]" in result
    assert "john@example.com" not in result


def test_empty_text_is_safe():
    guardrail = PIIGuardrail()

    result = guardrail.inspect("")

    assert result.contains_pii is False
