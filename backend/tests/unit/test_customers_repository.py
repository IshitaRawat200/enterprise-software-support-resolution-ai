import asyncio
from types import SimpleNamespace
from uuid import uuid4

from app.database.repositories.customers import CustomerRepository


class FakeResult:
    def __init__(self, scalar_one_or_none=None):
        self._scalar = scalar_one_or_none

    def scalar_one_or_none(self):
        return self._scalar


class FakeSession:
    def __init__(self):
        self.next_result = None
        self.added = []
        self.flushed = False
        self.refreshed = []

    async def execute(self, *args, **kwargs):
        return self.next_result

    def add(self, obj):
        self.added.append(obj)

    async def flush(self):
        self.flushed = True

    async def refresh(self, obj):
        self.refreshed.append(obj)


def make_customer():
    # use a lightweight SimpleNamespace instead of the ORM-mapped Customer
    return SimpleNamespace(customer_code="C1", user_id=uuid4(), contact_name="A")


def test_get_by_variants():
    fs = FakeSession()
    c = make_customer()
    fs.next_result = FakeResult(scalar_one_or_none=c)
    repo = CustomerRepository(session=fs)

    assert asyncio.run(repo.get_by_id(uuid4())) is c
    assert asyncio.run(repo.get_by_user_id(uuid4())) is c
    assert asyncio.run(repo.get_by_customer_code("C1")) is c


def test_create_calls_session_methods():
    fs = FakeSession()
    repo = CustomerRepository(session=fs)
    cust = make_customer()
    out = asyncio.run(repo.create(cust))
    assert fs.flushed is True
    assert fs.refreshed and fs.refreshed[0] is out
    assert fs.added and fs.added[0] is out
