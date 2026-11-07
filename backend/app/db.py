"""MongoDB connection: Echo's long-term memory.

Uses PyMongo's built-in async client (the successor to the deprecated Motor driver).
Other modules get collections with `get_db()["users"]` etc.
"""

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
    for name in COLLECTIONS[1:]:
        await db[name].create_index([("user_id", ASCENDING)])

    await db.style_profiles.create_index([("user_id", ASCENDING)], unique=True)
    # "key" is the case-folded word, so "Zeynep" and "zeynep" are one entry.
    await db.personal_words.create_index(
        [("user_id", ASCENDING), ("key", ASCENDING)], unique=True
    )
    await db.utterances.create_index([("user_id", ASCENDING), ("status", ASCENDING)])
    await db.utterances.create_index(
        [("session_id", ASCENDING), ("created_at", DESCENDING)]
    )


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
