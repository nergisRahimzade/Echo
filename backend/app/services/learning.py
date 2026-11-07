"""The learning loop: what happens when a sentence is approved (filled in during phase 5)."""

import logging

logger = logging.getLogger("echo.learning")


async def on_approved(db, utterance: dict) -> None:
    """Called after an utterance is approved (thumbs up, auto-approved, or helper fix)."""
    logger.info("approved utterance %s", utterance.get("_id"))
