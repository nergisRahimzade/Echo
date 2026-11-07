import asyncio
from datetime import UTC, datetime

from bson import ObjectId


def make_utt(db, user_id, action="speak", attempt=1, status=None):
    doc = {"user_id": user_id, "session_id": "s", "speaker": "user", "sentence": "Su istiyorum.", "action": action,
           "attempt": attempt, "status": status or ("spoken" if action == "speak" else "pending"), "created_at": datetime.now(UTC)}
    return str(asyncio.run(db.utterances.insert_one(doc)).inserted_id)


def get(db, uid):
    return asyncio.run(db.utterances.find_one({"_id": ObjectId(uid)}))


def fb(client, uid, verdict, **kw):
    return client.post("/feedback", json={"utterance_id": uid, "verdict": verdict, **kw})


def test_thumbs_up_after_check_means_speak(client, user_id, fake_db):
    uid = make_utt(fake_db, user_id, action="check")
    assert fb(client, uid, "up").json() == {"ok": True, "next_action": "speak"}
    assert get(fake_db, uid)["status"] == "approved"


def test_spoken_without_thumbs_down_is_auto_approved(client, user_id, fake_db):
    uid = make_utt(fake_db, user_id, action="speak")
    assert fb(client, uid, "up", auto=True).json()["next_action"] == "done"
    doc = get(fake_db, uid)
    assert doc["status"] == "approved" and doc["auto_approved"] is True


def test_first_thumbs_down_asks_to_repeat_second_calls_helper(client, user_id, fake_db):
    first = make_utt(fake_db, user_id, action="check", attempt=1)
    assert fb(client, first, "down").json()["next_action"] == "repeat"
    assert get(fake_db, first)["status"] == "rejected"
    second = make_utt(fake_db, user_id, action="check", attempt=2)
    assert fb(client, second, "down").json()["next_action"] == "helper"


def test_thumbs_down_on_spoken_sentence(client, user_id, fake_db):
    uid = make_utt(fake_db, user_id, action="speak")
    assert fb(client, uid, "down").json()["next_action"] == "repeat"
    assert get(fake_db, uid)["status"] == "rejected"


def test_helper_fix_is_saved_as_corrected(client, user_id, fake_db):
    uid = make_utt(fake_db, user_id, action="check", attempt=2, status="rejected")
    res = fb(client, uid, "down", final_text="  Pamuk nerede?  ")
    assert res.json()["next_action"] == "speak"
    doc = get(fake_db, uid)
    assert doc["status"] == "approved" and doc["final_text"] == "Pamuk nerede?" and doc["was_corrected"] is True


def test_unknown_or_other_persons_turn(client, user_id, fake_db):
    assert fb(client, str(ObjectId()), "up").status_code == 404
    assert fb(client, "nope", "up").status_code == 404
    turn = client.post("/turns", json={"user_id": user_id, "session_id": "s", "text": "hi"}).json()["turn_id"]
    assert fb(client, turn, "up").status_code == 404
    assert client.post("/feedback", json={"utterance_id": turn, "verdict": "maybe"}).status_code == 422
