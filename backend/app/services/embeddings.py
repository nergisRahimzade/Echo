"""Multilingual text embeddings (Voyage AI) so sentences match by meaning, in Turkish and English.

Optional: without EMBEDDING_API_KEY, `embed()` returns None and callers fall back to
spelling similarity.
"""

import logging

import httpx

from app.config import get_settings

logger = logging.getLogger("echo.embeddings")
VOYAGE_URL = "https://api.voyageai.com/v1/embeddings"


def enabled() -> bool:
    return bool(get_settings().embedding_api_key)


async def embed(texts: list[str], input_type: str = "document") -> list[list[float]] | None:
    """Vectors for `texts` ("document" for stored sentences, "query" for searches), or None."""
    s = get_settings()
    if not s.embedding_api_key or not texts:
        return None
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            res = await client.post(
                VOYAGE_URL,
                headers={"Authorization": f"Bearer {s.embedding_api_key}"},
                json={"input": texts, "model": s.embedding_model, "input_type": input_type},
            )
        res.raise_for_status()
        data = sorted(res.json()["data"], key=lambda d: d["index"])
        return [d["embedding"] for d in data]
    except (httpx.HTTPError, KeyError, ValueError) as exc:
        logger.warning("Embedding failed, falling back to spelling similarity: %s", exc)
        return None
