"""Task 6.5: the demo account (scripts/seed_demo.py) and GET /demo."""

import asyncio

from bson import ObjectId


def test_no_demo_account_is_404(client):
    assert client.get("/demo").status_code == 404


def test_seeded_sentences_show_as_learned(client, fake_db):
    from scripts import seed_demo

    uid = ObjectId()
    asyncio.run(fake_db.users.insert_one({
        "_id": uid, "name": "Deniz", "main_language": "both", "threshold": 0.78, "consent": True,
        "created_at": seed_demo.datetime.now(seed_demo.UTC), "demo": True,
    }))
    approved, corrected = asyncio.run(seed_demo.add_sentences(fake_db, str(uid), seed_demo.datetime.now(seed_demo.UTC)))
    assert approved >= 30 and corrected == 5

    demo = client.get("/demo").json()
    assert demo["user_id"] == str(uid) and demo["main_language"] == "both"
    progress = client.get(f"/users/{uid}/progress").json()
    assert progress["learned"] == approved and progress["corrected"] == corrected

    # Both languages are present, and helper corrections keep what was meant.
    docs = asyncio.run(fake_db.utterances.find({"user_id": str(uid), "speaker": "user"}).to_list(None))
    assert {d["language"] for d in docs} == {"tr", "en"}
    assert all(d.get("final_text") for d in docs if d["was_corrected"])
