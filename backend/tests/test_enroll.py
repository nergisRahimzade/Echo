import asyncio

import pytest
from bson import ObjectId

from tests.audio_utils import speech_like_webm

FAKE_WEBM = speech_like_webm()  # real (synthetic) webm/opus audio, like a browser recording


def post_sample(client, user_id, text="Su istiyorum", phrase_id="water", content_type="audio/webm;codecs=opus", data=FAKE_WEBM, **extra):
    form = {"user_id": user_id, "phrase_text": text, **extra}
    if phrase_id:
        form["phrase_id"] = phrase_id
    return client.post("/enroll", data=form, files={"audio": ("audio.webm", data, content_type)})


def test_three_recordings_saved_to_folder_and_db(client, fake_db, user_id, uploads_dir):
    phrases = [("hello", "Merhaba"), ("water", "Su istiyorum"), ("tired", "Yorgunum")]
    ids = []
    for pid, text in phrases:
        res = post_sample(client, user_id, text=text, phrase_id=pid)
        assert res.status_code == 201, res.text
        ids.append(res.json()["sample_id"])

    files = sorted(p.name for p in (uploads_dir / user_id).glob("*.webm"))
    assert files == sorted(f"{i}.webm" for i in ids)

    docs = asyncio.run(fake_db.enrollment_samples.find({"user_id": user_id}).to_list(None))
    assert len(docs) == 3
    doc = next(d for d in docs if d["phrase_id"] == "water")
    assert doc["text"] == "Su istiyorum"
    assert doc["language"] == "tr"  # defaulted from the user's main language
    assert doc["audio_path"] == f"{user_id}/{doc['_id']}.webm"
    assert (uploads_dir / doc["audio_path"]).read_bytes() == FAKE_WEBM


def test_list_samples(client, user_id):
    post_sample(client, user_id, text="Merhaba", phrase_id="hello")
    post_sample(client, user_id, text="Hello", phrase_id="hello", language="en")
    body = client.get(f"/enroll?user_id={user_id}").json()
    assert [(s["text"], s["language"]) for s in body] == [("Merhaba", "tr"), ("Hello", "en")]


def test_samples_get_wav_and_voiceprint(client, fake_db, user_id, uploads_dir):
    from app.services.voiceprint import MAX_FRAMES, N_MFCC, TEMPLATE_FRAMES

    sample_id = post_sample(client, user_id).json()["sample_id"]
    doc = asyncio.run(fake_db.enrollment_samples.find_one({"_id": ObjectId(sample_id)}))
    assert doc["wav_path"] == f"{user_id}/{sample_id}.wav"
    assert (uploads_dir / doc["wav_path"]).exists()
    assert len(doc["audio_vector"]) == TEMPLATE_FRAMES * N_MFCC
    assert 5 <= len(doc["audio_frames"]) <= MAX_FRAMES
    assert len(doc["audio_frames"][0]) == 2 * N_MFCC


def test_unreadable_audio_rejected(client, user_id, uploads_dir):
    res = post_sample(client, user_id, data=bytes([0x1A, 0x45, 0xDF, 0xA3]) + bytes(500))
    assert res.status_code == 422
    assert not any((uploads_dir / user_id).iterdir())


def test_safari_mp4_keeps_its_extension(client, user_id, uploads_dir):
    res = post_sample(client, user_id, content_type="audio/mp4")
    assert res.status_code == 201
    assert (uploads_dir / user_id / f"{res.json()['sample_id']}.mp4").exists()


def test_personal_word_without_phrase_id(client, user_id):
    assert post_sample(client, user_id, text="Zeynep", phrase_id=None).status_code == 201


def test_unknown_user_404(client):
    assert post_sample(client, str(ObjectId())).status_code == 404


@pytest.mark.parametrize(
    "kwargs, status",
    [
        ({"data": b""}, 400),
        ({"content_type": "text/plain"}, 415),
        ({"text": "   "}, 422),
        ({"language": "xx"}, 422),
    ],
)
def test_bad_uploads_rejected(client, user_id, uploads_dir, kwargs, status):
    assert post_sample(client, user_id, **kwargs).status_code == status
    folder = uploads_dir / user_id
    assert not folder.exists() or not any(folder.iterdir()), "nothing should be saved"


def test_too_large_rejected(client, user_id, monkeypatch):
    from app.config import get_settings

    monkeypatch.setenv("MAX_UPLOAD_MB", "0.001")
    get_settings.cache_clear()
    assert post_sample(client, user_id).status_code == 413
