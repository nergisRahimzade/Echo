from fastapi import APIRouter, HTTPException, Query

from app.services.phrases import Phrase, load_phrases, supported_languages

router = APIRouter(tags=["enrollment"])


@router.get("/phrases", response_model=list[Phrase])
async def get_phrases(lang: str = Query(..., min_length=2, max_length=8, examples=["tr"])):
    """The everyday phrases a new user repeats during enrollment, in one language."""
    try:
        return load_phrases(lang.lower())
    except KeyError:
        raise HTTPException(
            status_code=404,
            detail=f"No phrases for language '{lang}'. Available: {', '.join(supported_languages())}",
        ) from None
