import pytest

from app.services.scoring import candidate_agreement, combined_score, sound_match_similarity


def test_identical_candidates_and_strong_sound_match_score_above_080():
    s = combined_score(0.9, ["Su istiyorum."], "Su istiyorum.", [("Su istiyorum", 0.86), ("Yorgunum", 0.3)])
    assert s.candidate_agreement == 1.0
    assert s.sound_match == 0.86
    assert s.score >= 0.80  # 0.45 + 0.25 + 0.215


def test_three_agreeing_guesses_also_high():
    s = combined_score(0.85, ["Zeynep nerede?", "Zeynep nerede", "zeynep nerde"], "Zeynep nerede?", [("Zeynep nerede?", 0.8)])
    assert s.score >= 0.80


def test_messy_candidates_score_below_080():
    s = combined_score(0.6, ["Ben de yürürümüyorum", "Eğitim mümkün mü?", "Ben bir şey söyleyeyim"], "Ben bir şey söyleyeyim.", [("Su istiyorum", 0.14)])
    assert s.candidate_agreement < 0.6
    assert s.sound_match < 0.1
    assert s.score < 0.80


def test_confident_agent_alone_cannot_reach_080():
    # No agreement, no sound match: even a 100% sure agent stays below the bar.
    s = combined_score(1.0, ["xyz", "abc"], "Bambaşka bir cümle", [])
    assert s.score < 0.80


def test_partial_credit_for_similar_sound_match():
    full = sound_match_similarity([("Su istiyorum", 0.9)], "Su istiyorum.")
    partial = sound_match_similarity([("Su istiyorum", 0.9)], "Su istiyorum lütfen")
    none = sound_match_similarity([("Su istiyorum", 0.9)], "Kadıköy'e gidelim")
    assert full == 0.9 and none < partial < full


def test_edge_cases():
    assert candidate_agreement([], "x") == 0.0
    assert candidate_agreement(["x"], "") == 0.0
    assert sound_match_similarity([], "x") == 0.0
    assert combined_score(0.0, [], "", []).score == 0.0


def test_weights_come_from_config(monkeypatch):
    from app.config import get_settings

    monkeypatch.setenv("SCORE_WEIGHT_AGENT", "1.0")
    monkeypatch.setenv("SCORE_WEIGHT_AGREEMENT", "0")
    monkeypatch.setenv("SCORE_WEIGHT_SOUND", "0")
    get_settings.cache_clear()
    assert combined_score(0.7, ["a"], "b", []).score == pytest.approx(0.7)
