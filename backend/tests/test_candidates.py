import asyncio

import pytest

from app.services import asr
from app.services.asr import Transcript
from app.text import normalize, similarity


def fake_transcribe(replies):
    """Replace transcribe(): replies maps (prompt_used, temperature) -> text or Exception."""
    calls = []
    models = []

    async def _fake(wav, language=None, prompt=None, temperature=0.0, client=None, model=None):
        calls.append((bool(prompt), temperature))
        models.append(model)
        reply = replies[(bool(prompt), temperature)]
        if isinstance(reply, Exception):
            raise reply
        return Transcript(text=reply, language=language or "tr", prompt_used=bool(prompt), temperature=temperature)

    _fake.models = models
    return _fake, calls


def run(monkeypatch, replies, prompt="Zeynep, Kadıköy."):
    fake, calls = fake_transcribe(replies)
    monkeypatch.setattr(asr, "transcribe", fake)
    return asyncio.run(asr.get_candidates("x.wav", "tr", prompt)), calls


def test_three_variants_two_distinct(monkeypatch):
    cands, calls = run(monkeypatch, {(True, 0.0): "Zeynep geldi mi?", (False, 0.0): "Zeyneb geldi mi", (True, 0.4): "zeynep geldi mi"})
    assert sorted(calls) == [(False, 0.0), (True, 0.0), (True, 0.4)]
    assert [c.text for c in cands] == ["Zeynep geldi mi?", "Zeyneb geldi mi"]  # 3rd = duplicate of 1st


def test_extra_guess_uses_turbo_model_on_groq(monkeypatch):
    fake, _ = fake_transcribe({(True, 0.0): "a", (False, 0.0): "b", (True, 0.4): "c"})
    monkeypatch.setattr(asr, "transcribe", fake)
    asyncio.run(asr.get_candidates("x.wav", "tr", "Zeynep."))
    assert sorted(fake.models, key=str) == sorted([None, None, "whisper-large-v3-turbo"], key=str)


def test_no_prompt_makes_two_calls(monkeypatch):
    cands, calls = run(monkeypatch, {(False, 0.0): "Su istiyorum", (False, 0.4): "Su istiyorum."}, prompt="")
    assert len(calls) == 2 and [c.text for c in cands] == ["Su istiyorum"]


def test_one_failure_is_tolerated(monkeypatch):
    cands, _ = run(monkeypatch, {(True, 0.0): asr.ASRError("boom"), (False, 0.0): "Merhaba", (True, 0.4): "Merhaba!"})
    assert [c.text for c in cands] == ["Merhaba"]


def test_all_failures_raise(monkeypatch):
    err = asr.ASRError("down")
    with pytest.raises(asr.ASRError):
        run(monkeypatch, {(True, 0.0): err, (False, 0.0): err, (True, 0.4): err})


def test_prompt_echo_is_dropped(monkeypatch):
    cands, _ = run(monkeypatch, {(True, 0.0): "Zeynep, Kadıköy.", (False, 0.0): "Yorgunum", (True, 0.4): ""})
    assert [c.text for c in cands] == ["Yorgunum"]


def test_normalize_and_similarity():
    assert normalize("  İstanbul'a GİDİYORUZ!! ") == "istanbul'a gidiyoruz"
    assert normalize("Kadıköy, Şişli.") == "kadıköy şişli"
    assert similarity("Su istiyorum.", "su istiyorum") == 1.0
    assert 0.5 < similarity("Su istiyorum", "Su istiyoruz") < 1.0
    assert similarity("", "abc") == 0.0
