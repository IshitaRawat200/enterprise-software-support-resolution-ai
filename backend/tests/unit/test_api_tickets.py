import asyncio
from types import SimpleNamespace
from uuid import uuid4

import app.api.tickets as tickets_api


def test_create_ticket_success(monkeypatch):
    # Patch get_current_customer to return a fake customer
    async def fake_get_current_customer(current_user, session):
        return SimpleNamespace(id=uuid4())

    monkeypatch.setattr(
        tickets_api,
        "get_current_customer",
        fake_get_current_customer,
    )

    class FakeService:
        def __init__(self, session):
            pass

        async def create_customer_ticket(self, **kwargs):
            return SimpleNamespace(
                id=uuid4(),
                ticket_number="TICK-1",
                customer_id=kwargs.get("customer_id"),
                status="open",
                severity=kwargs.get("severity"),
                escalation_required=False,
            )

    monkeypatch.setattr(tickets_api, "TicketService", FakeService)

    request = SimpleNamespace(subject="Help", description="Please help", severity="low")

    out = asyncio.run(
        tickets_api.create_ticket(
            request=request, current_user=SimpleNamespace(id="u1"), session=None
        )
    )

    assert out.ticket_number == "TICK-1"


def test_get_my_ticket_success(monkeypatch):
    async def fake_get_current_customer(current_user, session):
        return SimpleNamespace(id=uuid4())

    monkeypatch.setattr(
        tickets_api,
        "get_current_customer",
        fake_get_current_customer,
    )

    class FakeService:
        def __init__(self, session):
            pass

        async def get_customer_ticket(self, customer_id, ticket_id):
            return SimpleNamespace(
                id=uuid4(),
                ticket_number="TICK-2",
                customer_id=customer_id,
                status="open",
                severity="medium",
                escalation_required=False,
            )

    monkeypatch.setattr(tickets_api, "TicketService", FakeService)

    out = asyncio.run(
        tickets_api.get_my_ticket(
            ticket_id="0001-0001", current_user=SimpleNamespace(id="u1"), session=None
        )
    )

    assert out.ticket_number == "TICK-2"
