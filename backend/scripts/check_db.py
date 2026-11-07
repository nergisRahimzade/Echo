"""Check the MongoDB connection on its own (no other API keys needed).

Run from the backend folder:  python -m scripts.check_db
Reads MONGODB_URI / MONGODB_DB from backend/.env (or the environment), connects,
creates the collections + indexes, and prints what it finds.
"""

import asyncio
import os
import sys

from dotenv import dotenv_values

from app import db
from app.config import ENV_FILE


async def main() -> int:
    values = {**dotenv_values(ENV_FILE), **os.environ}
    uri = (values.get("MONGODB_URI") or "").strip()
    name = (values.get("MONGODB_DB") or "echo").strip()
    if not uri:
        print(f"MONGODB_URI is not set. Add it to {ENV_FILE}.")
        return 1

    await db.connect(uri, name)
    status = await db.ping()
    print(f"db: {status}")
    if status == "connected":
        database = db.get_db()
        for coll in sorted(await database.list_collection_names()):
            indexes = [i["name"] async for i in await database[coll].list_indexes()]
            print(f"  {coll}: {', '.join(indexes)}")
    await db.close()
    return 0 if status == "connected" else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
