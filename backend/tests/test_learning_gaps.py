"""Three learning gaps:
1. rejected attempts learn the sentence the user confirmed afterwards;
2. silent approvals count for less, and stop counting once a later thumbs-down disputes them;
3. enrollment phrases go into the Whisper hint.
"""

import asyncio
from datetime import UTC, datetime, timedelta

from bson import ObjectId

from app.services import asr
from app.services.asr import Transcript, build_prompt
from app.services.sound_match import load_references
from app.services.voiceprint import compute
from tests.audio_utils import speech_like

T0 = datetime(2026, 11, 8, 12, tzinfo=UTC)
VP = compute(speech_like(1))


def add(db, user_id, n, **fields):
    """The n-th recording of the conversation (n seconds after T0)."""
    doc = {"user_id": user_id, "session_id": "s", "speaker": "user", "sentence": "Sus diyorum.", "action": "check",
           "attempt": 1, "status": "pending", "audio_vector": VP.vector, "audio_frames": VP.frames,
           "created_at": T0 + timedelta(seconds=n), **fields}
    return str(asyncio.run(db.utterances.insert_one(doc)).inserted_id)


def get(db, uid):
    return asyncio.run(db.utterances.find_one({"_id": ObjectId(uid)}))


def fb(client, uid, verdict, **kw):
    return client.post("/feedback", json={"utterance_id": uid, "verdict": verdict, **kw}).json()


# ---------- 1. relabelling failed attempts ----------


def test_thumbs_up_on_attempt_2_relabels_attempt_1(client, user_id, fake_db):
    earlier_message = add(fake_db, user_id, 0, status="approved", sentence="Merhaba.", verdict="up")
    first = add(fake_db, user_id, 1, status="rejected", verdict="down")
    second = add(fake_db, user_id, 2, attempt=2, sentence="Su istiyorum.")
    fb(client, second, "up")
    doc = get(fake_db, first)
    assert doc["final_text"] == "Su istiyorum." and doc["relabelled_from"] == second
    assert doc["status"] == "rejected" and doc["sentence"] == "Sus diyorum."  # still a wrong guess
    assert "final_text" not in get(fake_db, earlier_message)


def test_helper_fix_relabels_every_earlier_attempt(client, user_id, fake_db):
    a1 = add(fake_db, user_id, 1, status="rejected", verdict="down")
    a2 = add(fake_db, user_id, 2, attempt=2, status="rejected", verdict="down", sentence="Su diyorum.")
    a3 = add(fake_db, user_id, 3, attempt=3, sentence="Sus istiyorum.")
    fb(client, a3, "down")
    fb(client, a3, "down", final_text="Su istiyorum.")
    assert get(fake_db, a1)["final_text"] == get(fake_db, a2)["final_text"] == "Su istiyorum."
    assert get(fake_db, a3)["status"] == "approved"


def test_silent_approval_does_not_relabel(client, user_id, fake_db):
    first = add(fake_db, user_id, 1, status="rejected", verdict="down")
    second = add(fake_db, user_id, 2, attempt=2, action="speak", status="spoken", sentence="Su istiyorum.")
    fb(client, second, "up", auto=True)
    assert "final_text" not in get(fake_db, first)


def test_relabelled_attempt_is_a_sound_reference_and_still_a_wrong_guess(client, user_id, fake_db):
    from app.services.sound_match import load_wrong_guesses

    first = add(fake_db, user_id, 1, status="rejected", verdict="down")
    second = add(fake_db, user_id, 2, attempt=2, sentence="Su istiyorum.")
    fb(client, second, "up")
    refs = {r["id"]: r for r in asyncio.run(load_references(fake_db, user_id))}
    assert refs[first]["text"] == "Su istiyorum." and refs[first]["weight"] == 1.0
    wrong = {r["id"]: r["text"] for r in asyncio.run(load_wrong_guesses(fake_db, user_id))}
    assert wrong[first] == "Sus diyorum."


# ---------- 2. silence is weaker than a thumbs-up ----------


def test_silent_examples_weigh_less_in_sound_matching(fake_db):
    add(fake_db, "u", 1, status="approved", sentence="Evet.", auto_approved=True)
    add(fake_db, "u", 2, status="approved", sentence="Hayır.", auto_approved=False)
    add(fake_db, "u", 3, status="approved", sentence="Yorgunum.", was_corrected=True, final_text="Yorgunum.")
    weights = {r["text"]: r["weight"] for r in asyncio.run(load_references(fake_db, "u"))}
    assert weights == {"Evet.": 0.85, "Hayır.": 1.0, "Yorgunum.": 1.15}


def test_thumbs_down_disputes_the_silent_example_the_guess_came_from(client, user_id, fake_db):
    silent = add(fake_db, user_id, 1, status="approved", sentence="Su istiyorum.", auto_approved=True, verdict="up")
    confirmed = add(fake_db, user_id, 2, status="approved", sentence="Su istiyorum", auto_approved=False, verdict="up")
    other = add(fake_db, user_id, 3, status="approved", sentence="Merhaba.", auto_approved=True, verdict="up")
    matches = [{"text": t, "score": 0.9, "source": "utterance", "ref_id": r, "corrected": False}
               for t, r in [("Su istiyorum.", silent), ("Su istiyorum", confirmed), ("Merhaba.", other)]]
    guess = add(fake_db, user_id, 4, sentence="Su istiyorum!", sound_matches=matches)
    fb(client, guess, "down")
    assert get(fake_db, silent)["disputed"] is True
    assert "disputed" not in get(fake_db, confirmed)  # a person confirmed that one
    assert "disputed" not in get(fake_db, other)  # not the sentence that was rejected
    texts = {r["id"] for r in asyncio.run(load_references(fake_db, user_id))}
    assert silent not in texts and confirmed in texts


def seed_hint(db, approved=(), enrolled=()):
    async def go():
        for i, (text, auto, extra) in enumerate(approved):
            await db.utterances.insert_one({"user_id": "u", "status": "approved", "sentence": text, "auto_approved": auto, **extra, "created_at": T0 + timedelta(seconds=i)})
        for i, (text, lang) in enumerate(enrolled):
            await db.enrollment_samples.insert_one({"user_id": "u", "text": text, "language": lang, "created_at": T0 + timedelta(seconds=i)})

    asyncio.run(go())


def test_one_silent_approval_stays_out_of_the_hint_two_get_in(fake_db):
    seed_hint(fake_db, approved=[("Sus diyorum.", True, {})])
    assert asyncio.run(build_prompt(fake_db, "u")) == ""
    seed_hint(fake_db, approved=[("Sus diyorum.", True, {})])
    assert asyncio.run(build_prompt(fake_db, "u")) == "Sus diyorum."


def test_disputed_sentences_leave_the_hint(fake_db):
    seed_hint(fake_db, approved=[("Sus diyorum.", False, {"disputed": True}), ("Merhaba.", False, {})])
    assert asyncio.run(build_prompt(fake_db, "u")) == "Merhaba."


# ---------- 3. enrollment phrases in the hint ----------


def test_new_user_hint_has_their_enrollment_phrases(fake_db):
    seed_hint(fake_db, enrolled=[("Su istiyorum", "tr"), ("Good morning", "en"), ("Yorgunum", "tr"), ("Yorgunum", "tr")])
    assert asyncio.run(build_prompt(fake_db, "u", language="tr")) == "Yorgunum. Su istiyorum."  # re-recorded first
    assert asyncio.run(build_prompt(fake_db, "u", language="both")) == "Yorgunum. Su istiyorum. Good morning."


def test_approved_sentences_come_first_and_enrollment_fills_up(fake_db):
    seed_hint(fake_db, approved=[("Su istiyorum.", False, {}), ("Su istiyorum.", False, {}), ("Merhaba", False, {})],
              enrolled=[("Su istiyorum", "tr"), ("Yorgunum", "tr"), ("Evet", "tr")])
    assert asyncio.run(build_prompt(fake_db, "u", top_phrases=3, language="tr")) == "Su istiyorum. Merhaba. Yorgunum."


def test_hearing_one_hint_sentence_is_not_an_echo(monkeypatch):
    prompt = "Zeynep, Kadıköy. Su istiyorum lütfen. Bugün çok yorgunum."

    async def fake(wav, language=None, prompt=None, temperature=0.0, client=None, model=None):
        text = {(True, 0.0): "Su istiyorum lütfen.", (False, 0.0): "Su istiyorum lütfen", (True, 0.4): "Zeynep, Kadıköy."}[(bool(prompt), temperature)]
        return Transcript(text=text, language="tr", prompt_used=bool(prompt), temperature=temperature)

    monkeypatch.setattr(asr, "transcribe", fake)
    [cand] = asyncio.run(asr.get_candidates("x.wav", "tr", prompt))
    assert cand.text == "Su istiyorum lütfen." and cand.prompt_used  # kept (merged with the unprompted reading)
    assert len(cand.readings or [cand.reading]) >= 1

    echo = Transcript(text="Su istiyorum lütfen. Bugün çok yorgunum.", language="tr", prompt_used=True)
    names = Transcript(text="Zeynep, Kadıköy.", language="tr", prompt_used=True)
    assert asr._is_hallucination(echo, prompt) and asr._is_hallucination(names, prompt)
