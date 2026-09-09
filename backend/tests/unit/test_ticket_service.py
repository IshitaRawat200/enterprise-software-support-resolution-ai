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
