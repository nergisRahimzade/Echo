"""Audio file storage. MVP: the local uploads/ folder (S3-compatible storage later).

Paths stored in MongoDB are relative to the uploads folder ("{user_id}/{file}"),
so the folder can move (or become a bucket) without rewriting the database.
"""

import shutil
from pathlib import Path

from fastapi import HTTPException, UploadFile
from starlette.concurrency import run_in_threadpool

from app.config import get_settings

# What browsers record: webm/opus (Chrome, Firefox, Android), mp4 (Safari/iOS), ogg, wav.
EXTENSIONS = {
    "audio/webm": "webm",
    "video/webm": "webm",  # some browsers label audio-only webm as video
    "audio/mp4": "mp4",
    "video/mp4": "mp4",
    "audio/x-m4a": "m4a",
    "audio/ogg": "ogg",
    "audio/wav": "wav",
    "audio/x-wav": "wav",
    "audio/wave": "wav",
    "audio/mpeg": "mp3",
}


def uploads_root() -> Path:
    return get_settings().uploads_dir


def absolute_path(relative: str) -> Path:
    return uploads_root() / relative


def extension_for(upload: UploadFile) -> str:
    """File extension from the upload's content type, falling back to its file name."""
    content_type = (upload.content_type or "").split(";")[0].strip().lower()
    if content_type in EXTENSIONS:
        return EXTENSIONS[content_type]
    # Only trust the file name when the type is missing or generic.
    if content_type in ("", "application/octet-stream"):
        suffix = Path(upload.filename or "").suffix.lstrip(".").lower()
        if suffix in set(EXTENSIONS.values()):
            return suffix
    raise HTTPException(status_code=415, detail=f"Unsupported audio type '{upload.content_type}'.")


async def save_upload(upload: UploadFile, user_id: str, file_id: str) -> tuple[str, int]:
    """Save an uploaded recording. Returns (relative path, size in bytes)."""
    ext = extension_for(upload)
    data = await upload.read()
    max_bytes = int(get_settings().max_upload_mb * 1024 * 1024)
    if not data:
        raise HTTPException(status_code=400, detail="The audio file is empty.")
    if len(data) > max_bytes:
        raise HTTPException(status_code=413, detail=f"Audio is larger than {get_settings().max_upload_mb} MB.")

    relative = f"{user_id}/{file_id}.{ext}"
    target = absolute_path(relative)

    def write() -> None:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)

    await run_in_threadpool(write)
    return relative, len(data)


async def delete_file(relative: str) -> None:
    await run_in_threadpool(lambda: absolute_path(relative).unlink(missing_ok=True))


async def delete_user_folder(user_id: str) -> None:
    folder = uploads_root() / user_id
    await run_in_threadpool(lambda: shutil.rmtree(folder, ignore_errors=True))
