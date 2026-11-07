import asyncio

from bson import ObjectId

from app.agent.run import AgentResult
from app.services import translate as pipeline
from app.services.asr import Transcript
from tests.audio_utils import speech_like_webm


def fake_ai(monkeypatch, sentence, confidence, seen):
    async def cands(*a, **k):
        return [Transcript(text=sentence, language="tr")]

    async def agent(ctx, candidates, matches, hint, **kw):
        seen.append({"matches": matches, "rejected": kw.get("rejected")})
        return AgentResult(sentence=sentence, confidence=confidence, language="tr", reason="r")

    monkeypatch.setattr(pipeline, "get_candidates", cands)
    monkeypatch.setattr(pipeline, "interpret", agent)


def say(client, user_id, seed=7):
    files = {"audio": ("a.webm", speech_like_webm(seed), "audio/webm")}
    return client.post("/translate", data={"user_id": user_id, "session_id": f"s-{ObjectId()}"}, files=files).json()


def test_saying_it_again_matches_the_approved_sentence_with_a_higher_score(client, user_id, monkeypatch):
    seen = []
    fake_ai(monkeypatch, "Hoşça kal.", 0.7, seen)
    first = say(client, user_id)
    assert first["action"] == "check" and first["score_parts"]["sound_match"] == 0.0  # never heard before
    client.post("/feedback", json={"utterance_id": first["utterance_id"], "verdict": "up"})

    second = say(client, user_id)
    assert seen[-1]["matches"][0][0] == "Hoşça kal."  # the approved sentence is now a sound reference
    assert second["score_parts"]["sound_match"] > 0.9
    assert second["score"] > first["score"]


def test_rejected_guess_is_shown_as_not_this_for_similar_recordings(client, user_id, monkeypatch):
    seen = []
    fake_ai(monkeypatch, "Sus diyorum.", 0.5, seen)
    first = say(client, user_id, seed=9)
    client.post("/feedback", json={"utterance_id": first["utterance_id"], "verdict": "down"})
    say(client, user_id, seed=9)  # same sound, new conversation
    assert "Sus diyorum." in seen[-1]["rejected"]


def test_approval_stores_text_embedding(client, user_id, fake_db, monkeypatch):
    from app.config import get_settings
    from app.services import embeddings

    monkeypatch.setenv("EMBEDDING_API_KEY", "k")
    get_settings.cache_clear()

    async def fake_embed(texts, input_type="document"):
        return [[0.5, 0.5]]

    monkeypatch.setattr(embeddings, "embed", fake_embed)
    fake_ai(monkeypatch, "Merhaba.", 0.6, [])
    utt = say(client, user_id)
    client.post("/feedback", json={"utterance_id": utt["utterance_id"], "verdict": "down", "final_text": "Günaydın."})
    doc = asyncio.run(fake_db.utterances.find_one({"_id": ObjectId(utt["utterance_id"])}))
    assert doc["text_vector"] == [0.5, 0.5]


def test_helper_fix_is_marked_and_weighted_for_the_next_try(client, user_id, monkeypatch):
    """After a helper fix, the next similar recording shows the agent a helper-corrected match."""
    seen = []
    fake_ai(monkeypatch, "Müzik.", 0.4, seen)
    utt = say(client, user_id, seed=11)
    client.post("/feedback", json={"utterance_id": utt["utterance_id"], "verdict": "down"})
    client.post("/feedback", json={"utterance_id": utt["utterance_id"], "verdict": "down", "final_text": "Bugün çok mutluyum"})
    say(client, user_id, seed=11)
    text, score, corrected = seen[-1]["matches"][0]
    assert text == "Bugün çok mutluyum" and corrected is True and score >= 0.99  # weighted x1.15, capped at 1
    assert "Müzik." in seen[-1]["rejected"]  # and the wrong guess is "not this"


def test_prompt_marks_helper_corrected_matches():
    from app.agent.prompt import build_user_message

    msg = build_user_message(["mzk"], [("Bugün çok mutluyum", 1.0, True), ("Evet", 0.3, False)], "tr")
    assert '"Bugün çok mutluyum" (1.00, helper-corrected)' in msg and '"Evet" (0.30)' in msg
