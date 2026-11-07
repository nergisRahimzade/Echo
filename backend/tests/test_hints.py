import asyncio
from datetime import UTC, datetime, timedelta

from app.services.asr import MAX_HINT_WORDS, build_prompt, learned_names


def seed(db, words=(), approved=()):
    t0 = datetime(2026, 11, 1, tzinfo=UTC)

    async def go():
        for i, w in enumerate(words):
            await db.personal_words.insert_one({"user_id": "u", "word": w, "kind": "person", "created_at": t0 + timedelta(seconds=i)})
        for text, n, corrected in approved:
            for _ in range(n):
                await db.utterances.insert_one({"user_id": "u", "status": "approved", "final_text": text, "was_corrected": corrected})

    asyncio.run(go())


def test_most_used_names_come_first(fake_db):
    seed(fake_db, words=["Ali", "Zeynep", "Pamuk"], approved=[("Zeynep nerede?", 3, False), ("Pamuk mama yedi mi?", 1, False)])
    prompt = asyncio.run(build_prompt(fake_db, "u"))
    assert prompt.startswith("Zeynep, Pamuk, Ali.")


def test_names_learned_from_approved_sentences(fake_db):
    # "Özgür" was never added as a personal word, but a helper typed it (counts double)
    seed(fake_db, words=["Zeynep"], approved=[("Can you call Özgür for me?", 1, True), ("Merhaba", 2, False)])
    prompt = asyncio.run(build_prompt(fake_db, "u"))
    assert prompt.startswith("Zeynep, Özgür.")
    assert "Can you call Özgür for me?" in prompt


def test_learned_names_rules():
    sentences = {"Özgür'ü aradın mı?": 1, "Bugün Özgür geldi.": 1, "Merhaba Ali.": 1, "Evet. Kadıköy güzel.": 3}
    names = learned_names(sentences, known=set())
    assert "Özgür" not in names  # first word of a sentence doesn't count (only 1 real mention here)
    assert "Kadıköy" not in names  # starts a sentence after a full stop
    assert learned_names({"Bugün Özgür geldi.": 2}, known=set()) == ["Özgür"]
    assert learned_names({"Bugün Özgür geldi.": 2}, known={"özgür"}) == []


def test_hint_list_is_kept_short(fake_db):
    seed(fake_db, words=[f"İsim{i}" for i in range(30)])
    names = asyncio.run(build_prompt(fake_db, "u")).split(".")[0].split(", ")
    assert len(names) == MAX_HINT_WORDS


def test_every_approval_changes_the_next_prompt(fake_db):
    seed(fake_db, words=["Doruk"])
    before = asyncio.run(build_prompt(fake_db, "u"))
    seed(fake_db, approved=[("Topu Doruk'a ver.", 1, False)])
    after = asyncio.run(build_prompt(fake_db, "u"))
    assert before == "Doruk." and after == "Doruk. Topu Doruk'a ver."
