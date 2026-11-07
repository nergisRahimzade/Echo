import asyncio

from pymongo import ASCENDING

from app.db import COLLECTIONS, ensure_schema


def indexes(db, name):
    async def go():
        cursor = db[name].list_indexes()
        if asyncio.iscoroutine(cursor):
            cursor = await cursor
        return {i["name"]: i async for i in cursor}

    return asyncio.run(go())


def test_schema_created_and_repeatable(fake_db):
    asyncio.run(ensure_schema(fake_db))
    asyncio.run(ensure_schema(fake_db))  # running twice is fine
    assert set(COLLECTIONS) <= set(asyncio.run(fake_db.list_collection_names()))
    assert "user_id_1_key_1" in indexes(fake_db, "personal_words")
    assert {"user_id_1_status_1", "session_id_1_created_at_-1"} <= set(indexes(fake_db, "utterances"))
    assert indexes(fake_db, "style_profiles")["user_id_1"].get("unique") is True


def test_old_plain_style_profile_index_is_replaced(fake_db):
    """Older versions left a non-unique user_id_1 index; real MongoDB refused to redefine it."""
    asyncio.run(fake_db.style_profiles.create_index([("user_id", ASCENDING)]))
    assert not indexes(fake_db, "style_profiles")["user_id_1"].get("unique")
    asyncio.run(ensure_schema(fake_db))
    assert indexes(fake_db, "style_profiles")["user_id_1"].get("unique") is True
