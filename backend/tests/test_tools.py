import asyncio
import json
from datetime import UTC, datetime, timedelta

import httpx
import pytest

from app.agent import tools
from app.agent.tools import TOOL_DEFINITIONS, ToolContext, run_tool


def seed(db):
    t0 = datetime(2026, 11, 6, 12, tzinfo=UTC)

    async def go():
        await db.personal_words.insert_many([
            {"user_id": "u", "word": "Zeynep", "kind": "person", "created_at": t0},
            {"user_id": "u", "word": "Kadıköy", "kind": "place", "created_at": t0 + timedelta(seconds=1)},
            {"user_id": "x", "word": "Other", "kind": "person", "created_at": t0},
        ])
        await db.enrollment_samples.insert_one({"user_id": "u", "text": "Su istiyorum"})
        await db.utterances.insert_many([
            {"user_id": "u", "session_id": "s1", "status": "approved", "sentence": "Merhaba", "created_at": t0},
            {"user_id": "u", "session_id": "s1", "status": "turn", "speaker": "other", "sentence": "Ne yemek istersin?", "created_at": t0 + timedelta(seconds=5)},
            {"user_id": "u", "session_id": "s1", "status": "rejected", "sentence": "Yanlış tahmin", "created_at": t0 + timedelta(seconds=8)},
            {"user_id": "u", "session_id": "s1", "status": "approved", "sentence": "x", "final_text": "Makarna istiyorum", "created_at": t0 + timedelta(seconds=10)},
            {"user_id": "u", "session_id": "s0", "status": "approved", "sentence": "Makarna istiyorum", "created_at": t0 - timedelta(days=1)},
            {"user_id": "x", "session_id": "s1", "status": "approved", "sentence": "Başkası", "created_at": t0},
        ])
        await db.style_profiles.insert_one({"user_id": "u", "favourite_words": ["harika"], "formality": "casual", "updated_at": t0})

    asyncio.run(go())


@pytest.fixture
def ctx(fake_db):
    seed(fake_db)
    return ToolContext(db=fake_db, user_id="u", session_id="s1")


def call(ctx, name, args=None):
    return json.loads(asyncio.run(run_tool(ctx, name, args or {})))


def test_search_similar_sentences_lexical(ctx):
    hits = call(ctx, "search_similar_sentences", {"text": "makarna is tiyorum"})
    assert hits[0]["text"] == "Makarna istiyorum"
    assert hits[0]["times_said"] == 2
    texts = [h["text"] for h in hits]
    assert "Su istiyorum" in texts  # enrollment phrases count as known sentences
    assert "Yanlış tahmin" not in texts and "Başkası" not in texts


def test_get_personal_words(ctx):
    assert call(ctx, "get_personal_words") == [{"word": "Zeynep", "kind": "person"}, {"word": "Kadıköy", "kind": "place"}]


def test_get_style_profile(ctx, fake_db):
    assert call(ctx, "get_style_profile") == {"favourite_words": ["harika"], "formality": "casual"}
    assert call(ToolContext(db=fake_db, user_id="nobody"), "get_style_profile") == {"status": "no style profile yet"}


def test_get_recent_turns(ctx):
    turns = call(ctx, "get_recent_turns")
    assert turns == [
        {"speaker": "user", "text": "Merhaba"},
        {"speaker": "other person", "text": "Ne yemek istersin?"},
        {"speaker": "user", "text": "Makarna istiyorum"},
    ]


def test_recent_turns_without_session(fake_db):
    assert asyncio.run(tools.get_recent_turns(ToolContext(db=fake_db, user_id="u"))) == []


def test_unknown_tool(ctx):
    with pytest.raises(ValueError):
        asyncio.run(run_tool(ctx, "delete_everything", {}))


def test_definitions_are_strict_and_valid():
    assert {t["name"] for t in TOOL_DEFINITIONS} == {"search_similar_sentences", "get_personal_words", "get_style_profile", "get_recent_turns"}
    for t in TOOL_DEFINITIONS:
        assert t["strict"] is True and t["input_schema"]["additionalProperties"] is False


def test_vector_search_falls_back_when_index_missing(ctx, monkeypatch):
    """With an embedding key but no Atlas index (e.g. local Mongo), lexical search still answers."""
    from app.config import get_settings

    monkeypatch.setenv("EMBEDDING_API_KEY", "test-voyage")
    get_settings.cache_clear()

    async def fake_embed(texts, input_type="document"):
        return [[0.1] * 4 for _ in texts]

    monkeypatch.setattr(tools.embeddings, "embed", fake_embed)
    hits = call(ctx, "search_similar_sentences", {"text": "Merhaba"})
    assert hits[0]["text"] == "Merhaba"


def test_embed_calls_voyage(monkeypatch):
    from app.config import get_settings
    from app.services import embeddings

    monkeypatch.setenv("EMBEDDING_API_KEY", "test-voyage")
    get_settings.cache_clear()
    seen = []

    def handler(request):
        seen.append(json.loads(request.content))
        return httpx.Response(200, json={"data": [{"index": 1, "embedding": [2.0]}, {"index": 0, "embedding": [1.0]}]})

    real = httpx.AsyncClient
    monkeypatch.setattr(embeddings.httpx, "AsyncClient", lambda **kw: real(transport=httpx.MockTransport(handler)))
    assert asyncio.run(embeddings.embed(["a", "b"], "query")) == [[1.0], [2.0]]
    assert seen[0] == {"input": ["a", "b"], "model": "voyage-3.5", "input_type": "query"}


def test_embed_disabled_without_key(monkeypatch):
    from app.config import get_settings
    from app.services import embeddings

    monkeypatch.setenv("EMBEDDING_API_KEY", "")
    get_settings.cache_clear()
    assert asyncio.run(embeddings.embed(["a"])) is None
