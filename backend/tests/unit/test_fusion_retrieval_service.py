import asyncio
from types import SimpleNamespace

from app.rag.services.fusion_retrieval_service import (
    FusionRetrievalService,
)


def test_create_fusion_llm_raises_when_no_key(monkeypatch):
    # Force get_settings to return empty groq key
    monkeypatch.setattr(
        "app.rag.services.fusion_retrieval_service.get_settings",
        lambda: SimpleNamespace(groq_api_key="", groq_simple_model="m"),
    )

    svc = FusionRetrievalService(session=None)

    try:
        svc._create_fusion_llm()
    except RuntimeError as exc:
        assert "GROQ_API_KEY is not configured" in str(exc)


def test_build_retrieval_index_raises_when_no_chunks(monkeypatch):
    svc = FusionRetrievalService(session=None)

    class FakeRepo:
        async def list_chunks(self):
            return []

    svc.repository = FakeRepo()

    try:
        asyncio.run(svc._build_retrieval_index())
    except ValueError as exc:
        assert "No knowledge-base chunks are available" in str(exc)
