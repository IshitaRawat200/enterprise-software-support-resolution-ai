from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.services.ticket_service import TicketService


class FakeSession:
    def __init__(self):
        self.committed = False

    async def commit(self):
        self.committed = True


def make_service():
    fs = FakeSession()
    svc = TicketService(session=fs)

    # replace underlying repos with fakes
    svc.tickets = SimpleNamespace(
        create=lambda **kwargs: SimpleNamespace(id=uuid4(), **kwargs),
        get_by_id=lambda ticket_id: None,
        list_by_customer=lambda cid: [],
        find_active_for_customer=lambda cid: None,
        update=lambda ticket, values: ticket,
    )

    svc.messages = SimpleNamespace(
        create=lambda **kwargs: SimpleNamespace(id=uuid4(), **kwargs)
    )
    svc.audit = SimpleNamespace(
        create=lambda **kwargs: SimpleNamespace(id=uuid4(), **kwargs)
    )

    return svc, fs


def test_generate_ticket_number_format():
    assert TicketService.generate_ticket_number().startswith("TCK-")


def test_build_subject_truncation():
    long = "a" * 200
    subj = TicketService._build_subject(long)
    assert len(subj) <= 120


def test_build_subject_human_support_request():
    subject = TicketService._build_subject(
        "I need to speak to a human support agent. Please escalate this issue."
    )
    assert subject == "Human Support Request"


@pytest.mark.asyncio
async def test_create_customer_ticket_commits_and_messages_and_audit():
    svc, fs = make_service()

    # override tickets.create to return object with id
    async def fake_create(**kwargs):
        return SimpleNamespace(id=uuid4(), **kwargs)

    svc.tickets.create = fake_create

    # messages.create and audit.create are async in real code; patch them
    async def fake_msg_create(**kwargs):
        return SimpleNamespace(id=uuid4(), **kwargs)

    svc.messages.create = fake_msg_create

    async def fake_audit_create(**kwargs):
        return SimpleNamespace(id=uuid4(), **kwargs)

    svc.audit.create = fake_audit_create

    ticket = await svc.create_customer_ticket(
        customer_id=uuid4(), subject="s", description="d"
    )
    assert hasattr(ticket, "id")
    assert fs.committed is True


@pytest.mark.asyncio
async def test_create_ai_ticket_updates_existing_if_present(monkeypatch):
    svc, _ = make_service()

    existing = SimpleNamespace(id=uuid4(), customer_id=uuid4())

    async def fake_find_active(customer_id):
        return existing

    svc.find_active_ticket = fake_find_active

    called = {"updated": False}

    async def fake_update(ticket, values):
        called["updated"] = True
        return ticket

    svc.tickets.update = fake_update

    async def fake_msg_create(**kwargs):
        return SimpleNamespace(id=uuid4(), **kwargs)

    async def fake_audit_create(**kwargs):
        return SimpleNamespace(id=uuid4(), **kwargs)

    svc.messages.create = fake_msg_create
    svc.audit.create = fake_audit_create

    await svc.create_ai_ticket(
        customer_id=existing.customer_id,
        message="m",
        intent=None,
        route=None,
        severity="low",
        confidence=0.1,
        escalation_required=False,
        escalation_reason=None,
        ai_investigation_summary=None,
        request_id=uuid4(),
    )

    assert called["updated"] is True


@pytest.mark.asyncio
async def test_persist_ticket_and_escalation_uses_existing_ticket_service(monkeypatch):
    svc, fs = make_service()

    created_ticket = SimpleNamespace(
        id=uuid4(),
        ticket_number="TCK-12345678",
        customer_id=uuid4(),
    )
    created_escalation = SimpleNamespace(id=uuid4(), ticket_id=created_ticket.id)

    async def fake_create_ai_ticket(**kwargs):
        return created_ticket

    async def fake_escalation_create_or_update(**kwargs):
        return created_escalation

    async def fake_link_session(**kwargs):
        return None

    monkeypatch.setattr(svc, "create_ai_ticket", fake_create_ai_ticket)
    monkeypatch.setattr(
        "app.services.ticket_service.EscalationService.create_or_update",
        fake_escalation_create_or_update,
    )
    monkeypatch.setattr(svc, "link_session_to_ticket", fake_link_session)

    result = await svc.persist_ticket_and_escalation(
        customer_id=created_ticket.customer_id,
        message="I need to speak to a human support agent.",
        intent="billing",
        route="rag",
        severity="medium",
        confidence=0.9,
        escalation_required=True,
        escalation_reason="explicit user request",
        ai_investigation_summary="Needs human review.",
        request_id=uuid4(),
        session_id=uuid4(),
        handoff_context={"priority": "high", "type": "human_requested"},
        handoff_summary="Customer asks for human support.",
        recommended_action="Escalate to human support.",
    )

    assert result["ticket_id"] == created_ticket.id
    assert result["escalation_id"] == created_escalation.id
    assert result["escalation_required"] is True
    assert result["human_handoff_required"] is True
    assert result["escalation_reason"] == "Customer explicitly requested human support intervention."
    assert result["ticket_number"] == "TCK-12345678"
    assert result["handoff_context"]["priority"] == "high"
    assert result["handoff_context"]["type"] == "human_requested"


@pytest.mark.asyncio
async def test_create_ai_ticket_creates_fresh_ticket_for_explicit_human_handoff(monkeypatch):
    svc, _ = make_service()

    customer_id = uuid4()
    stale_ticket = SimpleNamespace(id=uuid4(), customer_id=customer_id)

    async def fake_find_active(customer_id):
        return stale_ticket

    created_ticket = SimpleNamespace(id=uuid4(), customer_id=customer_id)

    async def fake_create(**kwargs):
        created_ticket.ticket_number = kwargs["ticket_number"]
        created_ticket.subject = kwargs["subject"]
        created_ticket.description = kwargs["description"]
        created_ticket.intent = kwargs["intent"]
        created_ticket.route = kwargs["route"]
        return created_ticket

    async def fake_update(ticket, values):
        raise AssertionError("stale active ticket should not be updated")

    async def fake_msg_create(**kwargs):
        return SimpleNamespace(id=uuid4(), **kwargs)

    async def fake_audit_create(**kwargs):
        return SimpleNamespace(id=uuid4(), **kwargs)

    svc.find_active_ticket = fake_find_active
    svc.tickets.create = fake_create
    svc.tickets.update = fake_update
    svc.messages.create = fake_msg_create
    svc.audit.create = fake_audit_create

    ticket = await svc.create_ai_ticket(
        customer_id=customer_id,
        message="I need to speak to a human support agent. Please escalate this issue.",
        intent="human_handoff",
        route="incident",
        severity="low",
        confidence=0.95,
        escalation_required=True,
        escalation_reason="Human intervention required.",
        ai_investigation_summary="Human support requested.",
        request_id=uuid4(),
    )

    assert ticket.subject == "Human Support Request"
    assert ticket.description == (
        "I need to speak to a human support agent. Please escalate this issue."
    )


@pytest.mark.asyncio
async def test_get_customer_ticket_errors_when_not_found_and_permission():
    svc, _ = make_service()

    async def fake_get_by_id_none(ticket_id):
        return None

    svc.tickets.get_by_id = fake_get_by_id_none

    with pytest.raises(ValueError):
        await svc.get_customer_ticket(customer_id=uuid4(), ticket_id=uuid4())

    # now return ticket with mismatched customer
    async def fake_get_by_id(ticket_id):
        return SimpleNamespace(id=ticket_id, customer_id=uuid4())

    svc.tickets.get_by_id = fake_get_by_id

    with pytest.raises(PermissionError):
        await svc.get_customer_ticket(customer_id=uuid4(), ticket_id=uuid4())
