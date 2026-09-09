import asyncio
from types import SimpleNamespace
from uuid import uuid4

from app.database.repositories import ticket_repository as ticket_repo_mod
from app.database.repositories.ticket_repository import TicketRepository


class FakeResult:
    def __init__(self, scalar_one_or_none=None, scalars_list=None):
        self._scalar_one_or_none = scalar_one_or_none
        self._scalars_list = scalars_list or []

    def scalar_one_or_none(self):
        return self._scalar_one_or_none

    def scalars(self):
        return SimpleNamespace(all=lambda: self._scalars_list)


class FakeSession:
    def __init__(self):
        self.last_execute = None
        self.next_result = None
        self.added = []
        self.flushed = False

    async def execute(self, *args, **kwargs):
        self.last_execute = (args, kwargs)
        return self.next_result

    def add(self, obj):
        self.added.append(obj)

    async def flush(self):
        self.flushed = True


def make_ticket():
    # simple test double instead of constructing the ORM mapped class
    return SimpleNamespace(
        ticket_number="T123",
        customer_id=uuid4(),
        subject="sub",
        description="desc",
        intent=None,
        route=None,
        severity="low",
        confidence=0.5,
        escalation_required=False,
        escalation_reason=None,
        ai_investigation_summary=None,
    )


def test_get_and_list_and_find_active():
    fs = FakeSession()
    t = make_ticket()
    fs.next_result = FakeResult(scalar_one_or_none=t)
    repo = TicketRepository(session=fs)

    out = asyncio.run(repo.get_by_id(uuid4()))
    assert out is t

    fs.next_result = FakeResult(scalar_one_or_none=t)
    out2 = asyncio.run(repo.get_by_ticket_number("T123"))
    assert out2 is t

    fs.next_result = FakeResult(scalars_list=[t])
    lst = asyncio.run(repo.list_by_customer(uuid4()))
    assert isinstance(lst, list) and lst[0] is t

    fs.next_result = FakeResult(scalar_one_or_none=t)
    active = asyncio.run(repo.find_active_for_customer(uuid4()))
    assert active is t


def test_create_and_update_calls_flush_and_add():
    fs = FakeSession()
    repo = TicketRepository(session=fs)

    # Replace the SupportTicket mapped class with a lightweight fake to avoid mapper init
    class FakeTicket:
        def __init__(self, **kwargs):
            for k, v in kwargs.items():
                setattr(self, k, v)

    ticket_repo_mod.SupportTicket = FakeTicket

    ticket = asyncio.run(
        repo.create(
            ticket_number="T1",
            customer_id=uuid4(),
            subject="s",
            description="d",
            intent=None,
            route=None,
            severity="low",
            confidence=0.1,
            escalation_required=False,
            escalation_reason=None,
            ai_investigation_summary=None,
        )
    )

    assert fs.flushed is True
    assert fs.added and fs.added[0] is ticket

    updated = asyncio.run(repo.update(ticket, {"subject": "new", "confidence": 0.9}))
    assert updated.subject == "new"
    assert updated.confidence == 0.9
