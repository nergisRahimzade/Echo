import asyncio
from datetime import UTC, datetime, timedelta

from bson import ObjectId

from app.services import threshold
from app.services.threshold import decide


def w(speak_up=0, speak_down=0, check_up=0, check_down=0):
    return ([{"action": "speak", "verdict": "up"}] * speak_up + [{"action": "speak", "verdict": "down"}] * speak_down
            + [{"action": "check", "verdict": "up"}] * check_up + [{"action": "check", "verdict": "down"}] * check_down)


def test_rules():
    assert decide(0.80, w(speak_up=18, speak_down=2, check_up=5, check_down=5))[0] == 0.85  # 10% spoken wrong
    assert decide(0.80, w(speak_up=20, speak_down=1, check_up=5, check_down=4))[0] == 0.80  # 4.8%: fine
    assert decide(0.80, w(speak_up=10, check_up=19, check_down=1))[0] == 0.75  # 95% of checks were right
    assert decide(0.80, w(speak_up=10, check_up=9, check_down=1))[0] == 0.80  # exactly 90%: not more than
    assert decide(0.80, w(speak_down=5, check_up=20))[0] == 0.85  # both: safety wins
    assert decide(0.90, w(speak_down=5))[1] is None  # already at the top
    assert decide(0.70, w(check_up=30))[0] == 0.70  # already at the bottom


def simulate(db, user_id, rounds):
    """Each round: (speak_up, speak_down, check_up, check_down) answered sentences, then a review."""
    t = [datetime(2026, 11, 1, tzinfo=UTC)]
    seen = []

    async def go():
        for r in rounds:
            for item in w(*r):
                t[0] += timedelta(seconds=1)
                await db.utterances.insert_one({"user_id": user_id, "speaker": "user", "created_at": t[0], **item})
            await threshold.maybe_tune(db, user_id)
            u = await db.users.find_one({"_id": ObjectId(user_id)})
            seen.append(u["threshold"])

    asyncio.run(go())
    return seen


def test_simulated_run_moves_threshold_as_expected(client, user_id, fake_db):
    seen = simulate(fake_db, user_id, [
        (10, 0, 9, 0),   # 19 answered: too early to review
        (6, 0, 5, 0),    # 30: every check right (14/14) -> lower to 0.75
        (10, 0, 10, 0),  # 50: still every check right -> 0.70
        (10, 0, 10, 0),  # 70: would go lower, but 0.70 is the floor
        (8, 2, 5, 5),    # 90: 2/10 spoken were wrong -> back up to 0.75
        (5, 0, 5, 5),    # 105: only 15 since last review -> not yet
        (5, 0, 0, 0),    # 110: 20 since review, 50% checks right, 0 spoken wrong -> unchanged
    ])
    assert seen == [0.80, 0.75, 0.70, 0.70, 0.75, 0.75, 0.75]
    user = client.get(f"/users/{user_id}").json()
    assert [c["to"] for c in user["threshold_history"]] == [0.75, 0.70, 0.75]
    assert "thumbs-down" in user["threshold_history"][-1]["reason"]


def test_new_threshold_is_used_for_the_next_sentence(client, user_id, fake_db):
    simulate(fake_db, user_id, [(10, 0, 20, 0)])
    assert client.get(f"/users/{user_id}").json()["threshold"] == 0.75


def test_feedback_triggers_review(client, user_id, fake_db):
    t0 = datetime(2026, 11, 1, tzinfo=UTC)
    for i in range(29):
        asyncio.run(fake_db.utterances.insert_one({"user_id": user_id, "speaker": "user", "action": "check", "verdict": "up", "status": "approved", "created_at": t0 + timedelta(seconds=i)}))
    last = asyncio.run(fake_db.utterances.insert_one({"user_id": user_id, "session_id": "s", "speaker": "user", "action": "check", "status": "pending", "attempt": 1, "sentence": "x", "created_at": t0 + timedelta(minutes=5)})).inserted_id
    client.post("/feedback", json={"utterance_id": str(last), "verdict": "up"})
    assert client.get(f"/users/{user_id}").json()["threshold"] == 0.75
