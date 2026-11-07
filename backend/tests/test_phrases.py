import pytest
from fastapi.testclient import TestClient

from app.services.phrases import load_phrases, supported_languages


@pytest.fixture
def client():
    from app.main import app

    return TestClient(app)  # no `with`: skips startup, so no database is needed


def test_turkish_and_english_available():
    assert {"tr", "en"} <= set(supported_languages())


@pytest.mark.parametrize("lang", ["tr", "en"])
def test_twenty_valid_phrases(lang):
    phrases = load_phrases(lang)
    assert len(phrases) == 20
    assert len({p.id for p in phrases}) == 20, "ids must be unique"
    assert all(p.text.strip() and p.icon for p in phrases)
    # every category is covered, with short and long sentences mixed
    assert {p.category for p in phrases} == {"greetings", "needs", "feelings", "questions", "yes_no"}
    # (characters, not words: Turkish packs more meaning into each word)
    word_counts = [len(p.text.split()) for p in phrases]
    assert min(word_counts) == 1
    assert max(len(p.text) for p in phrases) >= 30


def test_same_phrase_ids_in_both_languages():
    tr = [(p.id, p.category, p.icon) for p in load_phrases("tr")]
    en = [(p.id, p.category, p.icon) for p in load_phrases("en")]
    assert tr == en


@pytest.mark.parametrize("lang", ["tr", "en", "TR"])
def test_endpoint_returns_twenty(client, lang):
    res = client.get(f"/phrases?lang={lang}")
    assert res.status_code == 200
    body = res.json()
    assert len(body) == 20
    assert set(body[0]) == {"id", "text", "category", "icon"}


def test_turkish_characters_survive(client):
    texts = [p["text"] for p in client.get("/phrases?lang=tr").json()]
    assert "Günaydın" in texts and "Çok teşekkür ederim" in texts


def test_unknown_language_is_404(client):
    res = client.get("/phrases?lang=xx")
    assert res.status_code == 404
    assert "Available: en, tr" in res.json()["detail"]


def test_language_is_required(client):
    assert client.get("/phrases").status_code == 422
