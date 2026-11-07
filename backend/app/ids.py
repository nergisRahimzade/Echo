"""Helpers for MongoDB ObjectIds in URLs and request bodies."""

from bson import ObjectId
from bson.errors import InvalidId
from fastapi import HTTPException


def parse_id(value: str, what: str = "item") -> ObjectId:
    """Turn an id string into an ObjectId, or answer 404 if it can't be one."""
    try:
        return ObjectId(value)
    except (InvalidId, TypeError):
        raise HTTPException(status_code=404, detail=f"{what.capitalize()} not found") from None


async def require_user(db, user_id: str) -> dict:
    """Load a user document or answer 404."""
    user = await db.users.find_one({"_id": parse_id(user_id, "user")})
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return user
