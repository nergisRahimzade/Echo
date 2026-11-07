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
        _fake.languages.append(language)
        models.append(model)
        reply = replies[(bool(prompt), temperature)]
        if isinstance(reply, Exception):
            raise reply
        return Transcript(text=reply, language=language or "tr", prompt_used=bool(prompt), temperature=temperature)

    _fake.models = models
    _fake.languages = []
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


def test_word_error_rate():
    from app.text import word_error_rate

    assert word_error_rate("Su istiyorum", "su istiyorum.") == 0.0
    assert word_error_rate("bir iki üç dört", "bir üç dört beş") == 0.5  # 1 deletion + 1 insertion
    assert word_error_rate("merhaba", "") == 1.0



def test_mixed_language_user_gets_one_reading_per_language_plus_auto(monkeypatch):
    seen = []

    async def fake(wav, language=None, prompt=None, temperature=0.0, client=None, model=None):
        seen.append(language)
        text = {"tr": "Merhaba", "en": "Bad Hubba", None: "大家好吧"}[language]
        detected = language or "chinese"
        return Transcript(text=text, language=detected, forced_language=language)

    monkeypatch.setattr(asr, "transcribe", fake)
    cands = asyncio.run(asr.get_candidates("x.wav", None, "Zeynep.", languages=["tr", "en"]))
    assert sorted(seen, key=str) == sorted(["tr", "en", None], key=str)
    # the auto-detected Chinese reading is dropped: this user speaks Turkish and English
    assert [(c.text, c.forced_language) for c in cands] == [("Merhaba", "tr"), ("Bad Hubba", "en")]


def test_known_whisper_hallucinations_are_dropped(monkeypatch):
    cands, _ = run(monkeypatch, {(True, 0.0): "Altyazı M.K.", (False, 0.0): "Hayır", (True, 0.4): "Thanks for watching!"})
    assert [c.text for c in cands] == ["Hayır"]


def test_certainty_words():
    assert Transcript(text="x", language="tr", avg_logprob=-0.2).certainty == "high"
    assert Transcript(text="x", language="tr", avg_logprob=-0.5).certainty == "medium"
    assert Transcript(text="x", language="tr", avg_logprob=-1.2).certainty == "low"



def test_identical_readings_are_merged_but_remembered(monkeypatch):
    async def fake(wav, language=None, prompt=None, temperature=0.0, client=None, model=None):
        return Transcript(text="I am tired.", language=language or "en", forced_language=language)

    monkeypatch.setattr(asr, "transcribe", fake)
    [cand] = asyncio.run(asr.get_candidates("x.wav", None, None, languages=["tr", "en"]))
    assert cand.readings == ["tr", "en", "auto:en"]

    from app.services.translate import describe_readings

    assert describe_readings(cand).startswith("[read as Turkish, read as English, auto-detected English;")
