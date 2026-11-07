import asyncio
import json
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace as NS

import pytest

from app.services import style

PROFILE = {
    "favourite_words": ["harika", "abi"], "common_phrases": ["Su istiyorum"], "typical_length": "short, 2-4 words",
    "formality": "casual", "humour": "none seen", "languages": "Turkish", "notes": "",
}


class FakeClaude:
    def __init__(self):
        self.calls = []
        self.beta = NS(messages=NS(create=self._create))

    async def _create(self, **kw):
        self.calls.append(kw)
        return NS(stop_reason="end_turn", content=[NS(type="text", text=json.dumps(PROFILE))])


def add_approved(db, user_id, n, start=0):
    t0 = datetime(2026, 11, 1, tzinfo=UTC)
    docs = [{"user_id": user_id, "speaker": "user", "status": "approved", "sentence": f"Cümle {i}", "created_at": t0 + timedelta(minutes=i)} for i in range(start, start + n)]
    asyncio.run(db.utterances.insert_many(docs))


def test_profile_built_from_latest_approved_sentences(fake_db):
    add_approved(fake_db, "u", 12)
    claude = FakeClaude()
    doc = asyncio.run(style.update_style_profile(fake_db, "u", client=claude))
    assert doc["favourite_words"] == ["harika", "abi"] and doc["based_on"] == 12
    sent = claude.calls[0]["messages"][0]["content"]
    assert sent.index("Cümle 11") < sent.index("Cümle 0")  # newest first
    assert claude.calls[0]["output_config"]["format"]["schema"] == style.STYLE_SCHEMA
    saved = asyncio.run(fake_db.style_profiles.find_one({"user_id": "u"}))
    assert saved["formality"] == "casual"


def test_due_every_10_approvals(fake_db):
    add_approved(fake_db, "u", 9)
    assert asyncio.run(style.due(fake_db, "u")) is False
    add_approved(fake_db, "u", 1, start=9)
    assert asyncio.run(style.due(fake_db, "u")) is True
    asyncio.run(fake_db.style_profiles.insert_one({"user_id": "u", "based_on": 10}))
    add_approved(fake_db, "u", 9, start=10)
    assert asyncio.run(style.due(fake_db, "u")) is False  # 19 approved, profile built on 10
    add_approved(fake_db, "u", 1, start=19)
    assert asyncio.run(style.due(fake_db, "u")) is True


def test_tenth_approval_updates_profile_in_background(client, user_id, fake_db, monkeypatch):
    """Ten thumbs-ups through the API -> the style profile appears, readable by the agent tool."""
    calls = []

    async def fake_summarize(sentences, client=None):
        calls.append(sentences)
        return PROFILE

    monkeypatch.setattr(style, "summarize_style", fake_summarize)
    ids = []
    for i in range(10):
        doc = {"user_id": user_id, "session_id": "s", "speaker": "user", "sentence": f"Cümle {i}", "action": "check", "status": "pending", "attempt": 1, "created_at": datetime.now(UTC)}
        ids.append(str(asyncio.run(fake_db.utterances.insert_one(doc)).inserted_id))
    for i, uid in enumerate(ids):
        client.post("/feedback", json={"utterance_id": uid, "verdict": "up"})
        if i < 9:
            assert not calls, "profile must not be built before 10 approvals"

    async def wait_for_profile():
        for _ in range(50):
            if await fake_db.style_profiles.find_one({"user_id": user_id}):
                return True
            await asyncio.sleep(0.02)
        return False

    assert asyncio.run(wait_for_profile())
    from app.agent.tools import ToolContext, get_style_profile

    profile = asyncio.run(get_style_profile(ToolContext(db=fake_db, user_id=user_id)))
    assert profile["favourite_words"] == ["harika", "abi"] and len(calls) == 1
