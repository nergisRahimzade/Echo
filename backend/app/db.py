"""MongoDB connection: Echo's long-term memory.

Uses PyMongo's built-in async client (the successor to the deprecated Motor driver).
Other modules get collections with `get_db()["users"]` etc.
"""

import inspect
import logging

from pymongo import ASCENDING, DESCENDING, AsyncMongoClient
from pymongo.asynchronous.database import AsyncDatabase

logger = logging.getLogger("echo.db")

# The 5 collections from the build plan.
COLLECTIONS = [
    "users",
    "enrollment_samples",
    "personal_words",
    "utterances",
    "style_profiles",
]

_client: AsyncMongoClient | None = None
_db: AsyncDatabase | None = None


async def connect(uri: str | None, db_name: str = "echo") -> None:
    """Open the connection and make sure every collection and index exists.

    Never raises: if the database is unreachable the server still starts,
    and /health reports the problem.
    """
    global _client, _db
    if not uri:
        logger.warning("MONGODB_URI is not set; running without a database.")
        return

    _client = AsyncMongoClient(uri, serverSelectionTimeoutMS=5000, tz_aware=True)
    _db = _client[db_name]
    try:
        await _client.admin.command("ping")
        await ensure_schema(_db)
        logger.info("Connected to MongoDB database '%s'.", db_name)
    except Exception as exc:  # network errors, bad credentials, IP not allow-listed...
        logger.error("Could not connect to MongoDB: %s", exc)


async def ensure_schema(db: AsyncDatabase) -> None:
    """Create missing collections and the indexes our queries rely on (safe to run repeatedly)."""
    existing = set(await db.list_collection_names())
    for name in COLLECTIONS:
        if name not in existing:
            await db.create_collection(name)

    # Almost every query is "things that belong to this user".
    for name in ("enrollment_samples", "personal_words", "utterances"):
        await db[name].create_index([("user_id", ASCENDING)])

    # One style profile per user. (An older version created a plain index with the same
    # auto-generated name "user_id_1"; real MongoDB refuses to redefine it, so replace it.)
    cursor = db.style_profiles.list_indexes()
    if inspect.isawaitable(cursor):  # real PyMongo async: await for the cursor; test double: already one
        cursor = await cursor
    indexes = {i["name"]: i async for i in cursor}
    if "user_id_1" in indexes and not indexes["user_id_1"].get("unique"):
        await db.style_profiles.drop_index("user_id_1")
    await db.style_profiles.create_index([("user_id", ASCENDING)], unique=True)
    # "key" is the case-folded word, so "Zeynep" and "zeynep" are one entry.
    await db.personal_words.create_index(
        [("user_id", ASCENDING), ("key", ASCENDING)], unique=True
    )
    await db.utterances.create_index([("user_id", ASCENDING), ("status", ASCENDING)])
    await db.utterances.create_index(
        [("session_id", ASCENDING), ("created_at", DESCENDING)]
    )
    await ensure_vector_index(db)


async def ensure_vector_index(db: AsyncDatabase, dims: int | None = None) -> None:
    """Atlas Vector Search index on approved sentences' text embeddings (Atlas only; best effort)."""
    from pymongo.operations import SearchIndexModel

    from app.config import get_settings

    dims = dims or get_settings().embedding_dims
    try:
        existing = [i["name"] async for i in await db.utterances.list_search_indexes()]
        if "utterance_text_vector" in existing:
            return
        await db.utterances.create_search_index(
            SearchIndexModel(
                name="utterance_text_vector",
                type="vectorSearch",
                definition={
                    "fields": [
                        {"type": "vector", "path": "text_vector", "numDimensions": dims, "similarity": "cosine"},
                        {"type": "filter", "path": "user_id"},
                        {"type": "filter", "path": "status"},
                    ]
                },
            )
        )
        logger.info("Created Atlas Vector Search index 'utterance_text_vector'.")
    except Exception as exc:  # not Atlas, no permission, or an older server
        logger.info("Vector search index not created (%s); similar-sentence search uses spelling similarity.", exc)


async def close() -> None:
    global _client, _db
    if _client is not None:
        await _client.close()
    _client = None
    _db = None


async def ping() -> str:
    """Return "connected", "disconnected" or "not configured" for /health."""
    if _client is None:
        return "not configured"
    try:
        await _client.admin.command("ping")
        return "connected"
    except Exception:
        return "disconnected"


class DatabaseUnavailable(RuntimeError):
    """The server is running without a database; API routes turn this into HTTP 503."""


def get_db() -> AsyncDatabase:
    """The Echo database. Raises DatabaseUnavailable if the server started without one."""
    if _db is None:
        raise DatabaseUnavailable("Database is not connected. Check MONGODB_URI.")
    return _db


def set_db(database: AsyncDatabase | None) -> None:
    """Swap in a database directly (used by tests with an in-memory fake)."""
    global _db
    _db = database


async def aggregate(collection, pipeline: list[dict]) -> list[dict]:
    """Run an aggregation and return all results.

    (PyMongo's async aggregate() must be awaited to get the cursor; the in-memory test
    double returns the cursor directly. This works with both.)
    """
    cursor = collection.aggregate(pipeline)
    if inspect.isawaitable(cursor):
        cursor = await cursor
    return [doc async for doc in cursor]
