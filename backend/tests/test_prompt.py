import json
import re

from app.agent.prompt import OUTPUT_SCHEMA, SYSTEM_PROMPT, build_user_message


def test_rules_present():
    for rule in ("Translate, never invent", "exactly ONE sentence", "language they spoke", "Return JSON only"):
        assert rule in SYSTEM_PROMPT


def test_three_worked_examples_in_both_languages():
    examples = re.findall(r"<example>(.*?)</example>", SYSTEM_PROMPT, re.S)
    assert len(examples) == 3
    outputs = [json.loads(re.search(r"Output: (\{.*\})", e.replace("\\\n", ""), re.S).group(1)) for e in examples]
    assert {o["language"] for o in outputs} == {"tr", "en"}
    for o in outputs:
        assert set(o) == set(OUTPUT_SCHEMA["required"])
        assert 0 <= o["confidence"] <= 1


def test_prompt_is_stable_for_caching():
    # No timestamps / per-request data in the cached system prompt.
    assert not re.search(r"\d{4}-\d{2}-\d{2}", SYSTEM_PROMPT)


def test_user_message_contains_everything():
    msg = build_user_message(
        ["Su is tiyo rum", "Sus diyorum"],
        [("Su istiyorum", 0.86)],
        "tr",
        personal_words=[("Zeynep", "person")],
        recent_turns=[("other person", "Ne istersin?")],
        rejected=["Sus diyorum."],
    )
    for part in ('"Su is tiyo rum" | "Sus diyorum"', '"Su istiyorum" (0.86)', "Zeynep (person)", 'other person: "Ne istersin?"', "Not this"):
        assert part in msg


def test_user_message_without_input():
    msg = build_user_message([], [], None)
    assert "heard nothing clear" in msg and "no earlier recordings" in msg
