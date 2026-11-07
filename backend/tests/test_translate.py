import asyncio

import pytest
from bson import ObjectId

from app.agent.run import AgentError, AgentResult
from app.services import translate as pipeline
from app.services.asr import Transcript
from tests.audio_utils import speech_like_webm


@pytest.fixture
def fake_ai(monkeypatch):
    """Replace Whisper and Claude with controllable fakes."""
    state = {"candidates": ["Su istiyorum.", "Su istiyorum"], "agent": AgentResult(sentence="Su istiyorum.", confidence=0.9, language="tr", reason="agree"), "seen": {}}

    async def fake_candidates(wav, language, prompt):
        state["seen"]["whisper_language"] = language
        state["seen"]["prompt"] = prompt
        return [Transcript(text=t, language="tr") for t in state["candidates"]]

    async def fake_interpret(ctx, candidates, matches, language_hint, **kw):
        state["seen"]["agent_input"] = {"candidates": candidates, "matches": matches, **kw}
        if isinstance(state["agent"], Exception):
            raise state["agent"]
        return state["agent"]

    monkeypatch.setattr(pipeline, "get_candidates", fake_candidates)
    monkeypatch.setattr(pipeline, "interpret", fake_interpret)
    return state


def enroll(client, user_id, text="Su istiyorum", seed=0):
    files = {"audio": ("a.webm", speech_like_webm(seed), "audio/webm")}
    assert client.post("/enroll", data={"user_id": user_id, "phrase_text": text}, files=files).status_code == 201


def send(client, user_id, session="s1", seed=0):
    files = {"audio": ("a.webm", speech_like_webm(seed), "audio/webm")}
    return client.post("/translate", data={"user_id": user_id, "session_id": session}, files=files)


def test_known_phrase_is_spoken(client, user_id, fake_db, fake_ai):
    enroll(client, user_id)
    client.post("/words", json={"user_id": user_id, "words": [{"word": "Zeynep", "kind": "person"}]})
    res = send(client, user_id)
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["sentence"] == "Su istiyorum."
    assert body["action"] == "speak" and body["score"] >= 0.8
    assert body["language"] == "tr" and body["attempt"] == 1
    assert set(body["score_parts"]) == {"score", "agent_confidence", "candidate_agreement", "sound_match"}
    assert body["score_parts"]["sound_match"] > 0.9  # same audio as the enrolled sample
    # the agent saw the sound match and the personal words; Whisper got the user's language + hints
    assert fake_ai["seen"]["agent_input"]["matches"][0][0] == "Su istiyorum"  # (text, score, corrected)
    assert fake_ai["seen"]["agent_input"]["personal_words"] == [("Zeynep", "person")]
    assert fake_ai["seen"]["whisper_language"] == "tr" and "Zeynep" in fake_ai["seen"]["prompt"]

    doc = asyncio.run(fake_db.utterances.find_one({"_id": ObjectId(body["utterance_id"])}))
    assert doc["status"] == "spoken" and doc["attempt"] == 1 and doc["action"] == "speak"
    assert doc["audio_vector"] and doc["wav_path"].endswith(".wav")
    assert "total" in doc["timings"]


def test_unsure_result_is_checked(client, user_id, fake_ai):
    fake_ai["candidates"] = ["Ben de yürürümüyorum", "Eğitim mümkün mü?"]
    fake_ai["agent"] = AgentResult(sentence="Ben bir şey söyleyeyim.", confidence=0.35, language="tr", reason="unsure")
    body = send(client, user_id).json()
    assert body["action"] == "check" and body["score"] < 0.8


def test_users_threshold_is_used(client, user_id, fake_db, fake_ai):
    enroll(client, user_id)
    asyncio.run(fake_db.users.update_one({"_id": ObjectId(user_id)}, {"$set": {"threshold": 0.99}}))
    assert send(client, user_id).json()["action"] == "check"


def test_agent_failure_falls_back_to_check(client, user_id, fake_ai):
    fake_ai["agent"] = AgentError("Claude down")
    body = send(client, user_id).json()
    assert body["sentence"] == "Su istiyorum."  # best Whisper guess
    assert body["action"] == "check"  # never spoken without the agent
    assert "Agent unavailable" in body["reason"]


def test_attempt_counts_and_rejections_are_passed(client, user_id, fake_db, fake_ai):
    first = send(client, user_id).json()
    asyncio.run(fake_db.utterances.update_one({"_id": ObjectId(first["utterance_id"])}, {"$set": {"status": "rejected"}}))
    second = send(client, user_id).json()
    assert second["attempt"] == 2
    assert fake_ai["seen"]["agent_input"]["rejected"] == ["Su istiyorum."]
    assert send(client, user_id, session="other").json()["attempt"] == 1


def test_mixed_language_user_gets_auto_detect(client, fake_ai):
    uid = client.post("/users", json={"name": "M", "main_language": "both", "consent": True}).json()["user_id"]
    fake_ai["agent"] = AgentResult(sentence="Bugün çok happy.", confidence=0.8, language="mixed", reason="mix")
    body = send(client, uid).json()
    assert fake_ai["seen"]["whisper_language"] is None
    assert body["language"] == "tr"  # voice picked from what Whisper detected


def test_bad_audio_and_unknown_user(client, user_id, fake_ai):
    bad = client.post("/translate", data={"user_id": user_id, "session_id": "s"}, files={"audio": ("a.webm", bytes(300), "audio/webm")})
    assert bad.status_code == 422
    assert send(client, str(ObjectId())).status_code == 404
