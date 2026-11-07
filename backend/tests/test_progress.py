import asyncio
from datetime import UTC, datetime


def approve(db, user_id, n, corrected=False):
    docs = [{"user_id": user_id, "speaker": "user", "status": "approved", "was_corrected": corrected, "created_at": datetime.now(UTC)} for _ in range(n)]
    asyncio.run(db.utterances.insert_many(docs))


def test_progress_grows_with_each_approval(client, user_id, fake_db):
    p0 = client.get(f"/users/{user_id}/progress").json()
    assert p0["learned"] == 0 and p0["fraction"] == 0 and p0["milestone"] == 10
    approve(fake_db, user_id, 1)
    p1 = client.get(f"/users/{user_id}/progress").json()
    assert p1["learned"] == 1 and p1["fraction"] == 0.1
    approve(fake_db, user_id, 41)
    approve(fake_db, user_id, 1, corrected=True)
    p2 = client.get(f"/users/{user_id}/progress").json()
    assert p2["learned"] == 43 and p2["corrected"] == 1 and p2["milestone"] == 50
    assert p2["fraction"] == round((43 - 25) / (50 - 25), 3)


def test_progress_counts_enrollment_and_words(client, user_id, fake_db):
    asyncio.run(fake_db.enrollment_samples.insert_one({"user_id": user_id, "text": "x"}))
    client.post("/words", json={"user_id": user_id, "words": [{"word": "Zeynep"}]})
    p = client.get(f"/users/{user_id}/progress").json()
    assert p["enrollment_samples"] == 1 and p["personal_words"] == 1 and p["threshold"] == 0.8
