import asyncio
from datetime import UTC, datetime, timedelta

from bson import ObjectId

from app.services.learning import approve_unanswered_spoken
from tests.audio_utils import speech_like_webm


def insert(db, user_id, **fields):
    doc = {"user_id": user_id, "session_id": "s", "speaker": "user", "sentence": "Merhaba", "action": "speak",
           "status": "spoken", "audio_path": f"{user_id}/a.webm", "created_at": datetime.now(UTC), **fields}
    return asyncio.run(db.utterances.insert_one(doc)).inserted_id


def test_unanswered_spoken_sentences_count_as_approved(fake_db, user_id):
    old = insert(fake_db, user_id, created_at=datetime.now(UTC) - timedelta(seconds=30))
    fresh = insert(fake_db, user_id)  # still inside its 5 s window
    flagged = insert(fake_db, user_id, created_at=datetime.now(UTC) - timedelta(seconds=30), status="rejected", verdict="down")
    assert asyncio.run(approve_unanswered_spoken(fake_db, user_id)) == 1
    get = lambda i: asyncio.run(fake_db.utterances.find_one({"_id": i}))
    assert get(old)["status"] == "approved" and get(old)["auto_approved"] is True
    assert get(fresh)["status"] == "spoken"
    assert get(flagged)["status"] == "rejected"


def test_approved_and_rejected_listed_with_audio(client, user_id, fake_db):
    a = insert(fake_db, user_id, status="approved", verdict="up", was_corrected=False, score={"score": 0.91})
    r = insert(fake_db, user_id, status="rejected", verdict="down", sentence="Yanlış")
    client.post("/turns", json={"user_id": user_id, "session_id": "s", "text": "other person"})
    everything = client.get(f"/utterances?user_id={user_id}").json()
    assert {u["utterance_id"] for u in everything} == {str(a), str(r)}  # other person's turns excluded
    approved = client.get(f"/utterances?user_id={user_id}&status=approved").json()
    assert len(approved) == 1 and approved[0]["score"] == 0.91 and approved[0]["audio_path"].endswith("a.webm")
    rejected = client.get(f"/utterances?user_id={user_id}&status=rejected").json()
    assert rejected[0]["sentence"] == "Yanlış" and rejected[0]["verdict"] == "down"


def test_full_round_trip_through_the_api(client, user_id, fake_db, monkeypatch):
    """translate -> thumbs down -> helper fix: the database ends up with the corrected sentence + audio."""
    from app.agent.run import AgentResult
    from app.services import translate as pipeline
    from app.services.asr import Transcript

    async def cands(*a, **k):
        return [Transcript(text="Sus diyorum", language="tr")]

    async def agent(*a, **k):
        return AgentResult(sentence="Sus diyorum.", confidence=0.4, language="tr", reason="unsure")

    monkeypatch.setattr(pipeline, "get_candidates", cands)
    monkeypatch.setattr(pipeline, "interpret", agent)
    files = {"audio": ("a.webm", speech_like_webm(), "audio/webm")}
    utt = client.post("/translate", data={"user_id": user_id, "session_id": "s"}, files=files).json()
    assert utt["action"] == "check"
    client.post("/feedback", json={"utterance_id": utt["utterance_id"], "verdict": "down"})
    client.post("/feedback", json={"utterance_id": utt["utterance_id"], "verdict": "down", "final_text": "Su istiyorum."})
    [row] = client.get(f"/utterances?user_id={user_id}").json()
    assert row["status"] == "approved" and row["final_text"] == "Su istiyorum." and row["was_corrected"] is True
    assert row["audio_path"].startswith(user_id)
