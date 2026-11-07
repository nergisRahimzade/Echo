from bson import ObjectId


def add(client, user_id, *words):
    return client.post("/words", json={"user_id": user_id, "words": list(words)})


def test_words_saved_and_listed_back(client, user_id):
    res = add(client, user_id, {"word": "Zeynep", "kind": "person"}, {"word": " Kadıköy ", "kind": "place"}, {"word": "Pamuk", "kind": "pet"})
    assert res.status_code == 200
    assert res.json() == {"ok": True, "count": 3}
    words = client.get(f"/words?user_id={user_id}").json()
    assert words == [
        {"word": "Zeynep", "kind": "person"},
        {"word": "Kadıköy", "kind": "place"},  # trimmed
        {"word": "Pamuk", "kind": "pet"},
    ]


def test_same_word_different_case_is_one_entry(client, user_id):
    add(client, user_id, {"word": "zeynep", "kind": "other"})
    add(client, user_id, {"word": "Zeynep", "kind": "person"})
    assert client.get(f"/words?user_id={user_id}").json() == [{"word": "Zeynep", "kind": "person"}]


def test_kind_defaults_to_other(client, user_id):
    add(client, user_id, {"word": "Okul"})
    assert client.get(f"/words?user_id={user_id}").json()[0]["kind"] == "other"


def test_delete_word(client, user_id):
    add(client, user_id, {"word": "Ali", "kind": "person"}, {"word": "Ankara", "kind": "place"})
    assert client.delete(f"/words?user_id={user_id}&word=ali").status_code == 200
    assert [w["word"] for w in client.get(f"/words?user_id={user_id}").json()] == ["Ankara"]
    assert client.delete(f"/words?user_id={user_id}&word=ali").status_code == 404


def test_validation(client, user_id):
    assert add(client, user_id, {"word": "   "}).status_code == 422
    assert add(client, user_id, {"word": "X", "kind": "robot"}).status_code == 422
    assert client.post("/words", json={"user_id": user_id, "words": []}).status_code == 422


def test_words_are_per_user(client, user_id):
    other = client.post("/users", json={"name": "B", "main_language": "en", "consent": True}).json()["user_id"]
    add(client, user_id, {"word": "Zeynep"})
    assert client.get(f"/words?user_id={other}").json() == []


def test_unknown_user(client):
    assert add(client, str(ObjectId()), {"word": "A"}).status_code == 404
