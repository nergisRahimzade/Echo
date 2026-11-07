"""Add sound fingerprints to enrollment samples that don't have one (or have an old version).

Run from backend/:  python -m scripts.backfill_voiceprints
"""

import asyncio
import sys

from app import db
from app.config import get_settings
from app.services.audio import AudioError
from app.services.voiceprint import VERSION, fingerprint_upload


async def main() -> int:
    s = get_settings()
    await db.connect(s.mongodb_uri, s.mongodb_db)
    database = db.get_db()
    query = {"$or": [{"audio_vector": {"$exists": False}}, {"voiceprint_version": {"$ne": VERSION}}]}
    done = failed = 0
    async for doc in database.enrollment_samples.find(query):
        try:
            fields = await fingerprint_upload(doc["audio_path"])
        except (AudioError, FileNotFoundError) as exc:
            print(f"  skip {doc['_id']}: {exc}")
            failed += 1
            continue
        await database.enrollment_samples.update_one({"_id": doc["_id"]}, {"$set": fields})
        done += 1
    print(f"fingerprinted {done} samples, {failed} failed")
    await db.close()
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
