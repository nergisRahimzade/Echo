"""Thumbs up / thumbs down / helper fix for one translated sentence."""

from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, model_validator

from app.db import get_db
from app.ids import parse_id
from app.services import learning, threshold

router = APIRouter(tags=["conversation"])

# After this many wrong guesses in a row, stop guessing and ask a helper.
HELPER_AFTER_ATTEMPTS = 2


class FeedbackIn(BaseModel):
    utterance_id: str
    verdict: Literal["up", "down"]
    final_text: str | None = Field(None, max_length=500)  # helper fix only
    auto: bool = False  # True when a spoken sentence got no thumbs-down within 5 seconds

    @model_validator(mode="after")
    def tidy(self):
        if self.final_text is not None:
            self.final_text = self.final_text.strip() or None
        return self


@router.post("/feedback")
async def feedback(body: FeedbackIn) -> dict:
    """Record the user's verdict and say what the app should do next.

    next_action: "speak"  - say the sentence aloud now (thumbs up after a check)
                 "done"   - nothing more to do
                 "repeat" - ask the user to say it again
                 "helper" - second wrong guess: let the listener / a caregiver type it
    """
    db = get_db()
    utt = await db.utterances.find_one({"_id": parse_id(body.utterance_id, "utterance")})
    if utt is None or utt.get("speaker") == "other":
        raise HTTPException(status_code=404, detail="Utterance not found")

    now = datetime.now(UTC)
    update: dict = {"verdict": body.verdict, "feedback_at": now}

    if body.final_text:
        # A helper typed what was meant: that is the truth for this recording.
        update |= {"status": "approved", "final_text": body.final_text, "was_corrected": True, "verdict": "helper"}
        next_action = "speak"
    elif body.verdict == "up":
        update |= {"status": "approved", "was_corrected": False, "auto_approved": body.auto}
        next_action = "speak" if utt.get("action") == "check" else "done"
    else:
        update |= {"status": "rejected"}
        next_action = "helper" if int(utt.get("attempt", 1)) >= HELPER_AFTER_ATTEMPTS else "repeat"

    await db.utterances.update_one({"_id": utt["_id"]}, {"$set": update})
    if body.verdict == "down":
        # The guess was wrong (a helper fix is sent as "down" too).
        await learning.dispute_silent_matches(db, utt)
    if update["status"] == "approved":
        await learning.on_approved(db, {**utt, **update})
        if not body.auto:
            # Confirmed by a person: the earlier, rejected tries of this message meant it too.
            await learning.relabel_failed_attempts(db, utt, body.final_text or utt.get("sentence") or "")
    await threshold.maybe_tune(db, utt["user_id"])
    return {"ok": True, "next_action": next_action}
