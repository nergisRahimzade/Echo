import asyncio
from datetime import UTC, datetime

from bson import ObjectId


def test_other_persons_turn_is_saved_and_listed(client, user_id, fake_db):
    asyncio.run(fake_db.utterances.insert_one({"user_id": user_id, "session_id": "s1", "speaker": "user", "status": "approved", "sentence": "Merhaba", "created_at": datetime(2026, 1, 1, tzinfo=UTC)}))
    res = client.post("/turns", json={"user_id": user_id, "session_id": "s1", "text": "  Pamuk'u veterinere götürdük. "})
    assert res.status_code == 201
    turns = client.get(f"/turns?user_id={user_id}&session_id=s1").json()
    assert turns == [{"speaker": "user", "text": "Merhaba"}, {"speaker": "other person", "text": "Pamuk'u veterinere götürdük."}]
    assert client.get(f"/turns?user_id={user_id}&session_id=other").json() == []


def test_turn_validation(client, user_id):
    assert client.post("/turns", json={"user_id": user_id, "session_id": "s1", "text": "   "}).status_code == 422
    assert client.post("/turns", json={"user_id": str(ObjectId()), "session_id": "s1", "text": "hi"}).status_code == 404


def test_turns_do_not_count_as_rejected_attempts(client, user_id, fake_db):
    from app.services.translate import attempt_number

    asyncio.run(fake_db.utterances.insert_one({"user_id": user_id, "session_id": "s1", "speaker": "user", "status": "rejected", "sentence": "x", "created_at": datetime(2026, 1, 1, tzinfo=UTC)}))
    client.post("/turns", json={"user_id": user_id, "session_id": "s1", "text": "Tekrar söyler misin?"})
    assert asyncio.run(attempt_number(fake_db, user_id, "s1")) == 2
