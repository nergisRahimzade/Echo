"""Deleting everything Echo stores about a user (task 6.4: the user controls their voice data)."""

from app.services import storage, tts

USER_COLLECTIONS = ("enrollment_samples", "personal_words", "utterances", "style_profiles")


async def delete_everything(db, user: dict) -> dict:
    """Remove every document, every recording and the cached spoken audio of the user's sentences.

    `user` is the users document. Returns counts of what was removed.
    """
    user_id = str(user["_id"])
    texts: set[str] = set()
    async for u in db.utterances.find({"user_id": user_id}, {"sentence": 1, "final_text": 1}):
        texts.update(t for t in (u.get("sentence"), u.get("final_text")) if t)
    deleted = {name: (await db[name].delete_many({"user_id": user_id})).deleted_count for name in USER_COLLECTIONS}
    await db.users.delete_one({"_id": user["_id"]})
    await storage.delete_user_folder(user_id)
    cached = await tts.forget(texts)
    return {"deleted": deleted, "cached_audio_removed": cached}
