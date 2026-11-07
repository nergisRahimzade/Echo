"""Task 6.4: DELETE /users/{id}/data leaves nothing of that user in the database or uploads/."""

import asyncio

from bson import ObjectId

from app.services.privacy import USER_COLLECTIONS
from app.services import tts, voices


def seed(fake_db, uploads_dir, uid: str, sentence: str) -> None:
    async def go():
        for name in USER_COLLECTIONS:
            await fake_db[name].insert_one({"user_id": uid, "sentence": sentence, "final_text": sentence + "!"})

    asyncio.run(go())
    folder = uploads_dir / uid
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "sample.webm").write_bytes(b"audio")
    (folder / "sample.wav").write_bytes(b"audio")
    for text in (sentence, sentence + "!"):
        path = tts.cache_path(text, "tr", voices.get("will").elevenlabs_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"mp3")


def remaining(fake_db, uid: str) -> dict:
    async def go():
        counts = {name: await fake_db[name].count_documents({"user_id": uid}) for name in USER_COLLECTIONS}
        counts["users"] = await fake_db.users.count_documents({"_id": ObjectId(uid)})
        return counts

    return asyncio.run(go())


def test_delete_removes_everything_for_that_user_only(client, fake_db, uploads_dir):
    mine = client.post("/users", json={"name": "Ayşe", "main_language": "tr", "consent": True}).json()["user_id"]
    other = client.post("/users", json={"name": "Can", "main_language": "en", "consent": True}).json()["user_id"]
    seed(fake_db, uploads_dir, mine, "Su istiyorum")
    seed(fake_db, uploads_dir, other, "I am tired")

    res = client.delete(f"/users/{mine}/data")
    assert res.status_code == 200
    body = res.json()
    assert body["ok"] is True and body["deleted"]["utterances"] == 1 and body["cached_audio_removed"] == 2

    assert set(remaining(fake_db, mine).values()) == {0}  # nothing left in any collection
    assert not (uploads_dir / mine).exists()  # recordings gone
    assert not tts.cache_path("Su istiyorum", "tr", voices.get("will").elevenlabs_id).exists()  # spoken audio gone
    assert client.get(f"/users/{mine}").status_code == 404

    # The other user is untouched.
    assert set(remaining(fake_db, other).values()) == {1}
    assert (uploads_dir / other / "sample.webm").exists()
    assert tts.cache_path("I am tired", "tr", voices.get("will").elevenlabs_id).exists()


def test_delete_unknown_user_is_404(client):
    assert client.delete(f"/users/{ObjectId()}/data").status_code == 404
    assert client.delete("/users/not-an-id/data").status_code in (400, 404, 422)


def test_style_profile_not_recreated_after_delete(fake_db, monkeypatch):
    """A style rebuild that finishes after the user deleted their data must not save a profile."""
    from app.services import style

    uid = str(ObjectId())

    async def go():
        await fake_db.utterances.insert_one({"user_id": uid, "status": "approved", "sentence": "Su istiyorum"})

        async def slow_summary(sentences, client=None):
            await fake_db.utterances.delete_many({"user_id": uid})  # the delete happens meanwhile
            return {"summary": "short sentences"}

        monkeypatch.setattr(style, "summarize_style", slow_summary)
        assert await style.update_style_profile(fake_db, uid) is None
        return await fake_db.style_profiles.count_documents({"user_id": uid})

    assert asyncio.run(go()) == 0
