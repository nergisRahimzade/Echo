import asyncio
import json
from types import SimpleNamespace as NS

import pytest

from app.agent import run as agent_run
from app.agent.run import MAX_TOOL_ROUNDS, AgentError, interpret
from app.agent.tools import ToolContext


def text_reply(payload, stop="end_turn"):
    return NS(stop_reason=stop, content=[NS(type="text", text=json.dumps(payload) if not isinstance(payload, str) else payload)])


def tool_reply(*names):
    return NS(stop_reason="tool_use", content=[NS(type="tool_use", id=f"t{i}", name=n, input={"text": "su"} if n == "search_similar_sentences" else {}) for i, n in enumerate(names)])


class FakeClient:
    def __init__(self, replies):
        self.replies = list(replies)
        self.calls = []
        self.beta = NS(messages=NS(create=self._create))

    async def _create(self, **kwargs):
        self.calls.append(kwargs)
        return self.replies.pop(0)


GOOD = {"sentence": "Su istiyorum.", "confidence": 0.9, "language": "tr", "reason": "agree"}


@pytest.fixture
def ctx(fake_db):
    return ToolContext(db=fake_db, user_id="u", session_id="s")


def go(ctx, client, **kw):
    return asyncio.run(interpret(ctx, ["Su is tiyo rum", "Sus diyorum"], [("Su istiyorum", 0.86)], "tr", client=client, **kw))


def test_direct_answer(ctx):
    client = FakeClient([text_reply(GOOD)])
    r = go(ctx, client)
    assert r.sentence == "Su istiyorum." and r.confidence == 0.9 and r.language == "tr" and r.tool_calls == []
    call = client.calls[0]
    assert call["model"] == "claude-sonnet-5-5"
    assert call["output_config"]["format"]["type"] == "json_schema"
    assert call["fallbacks"] == "default" and call["betas"] == ["server-side-fallback-2026-07-01"]
    assert call["system"][0]["cache_control"] == {"type": "ephemeral"}
    assert '"Su is tiyo rum" | "Sus diyorum"' in call["messages"][0]["content"]


def test_tool_round_then_answer(ctx):
    client = FakeClient([tool_reply("search_similar_sentences", "get_personal_words"), text_reply(GOOD)])
    r = go(ctx, client)
    assert r.tool_calls == ["search_similar_sentences", "get_personal_words"]
    msgs = client.calls[1]["messages"]
    assert msgs[1]["role"] == "assistant"
    results = msgs[2]["content"]
    assert msgs[2]["role"] == "user" and [x["tool_use_id"] for x in results] == ["t0", "t1"]  # one message, all results


def test_tool_rounds_are_capped(ctx):
    client = FakeClient([tool_reply("get_style_profile")] * MAX_TOOL_ROUNDS + [text_reply(GOOD)])
    r = go(ctx, client)
    assert len(client.calls) == MAX_TOOL_ROUNDS + 1
    assert client.calls[-1]["tool_choice"] == {"type": "none"}
    assert all(c["tool_choice"] == {"type": "auto"} for c in client.calls[:-1])
    assert r.sentence == "Su istiyorum."


def test_tool_error_is_reported_not_fatal(ctx, monkeypatch):
    async def boom(ctx, name, args):
        raise RuntimeError("db down")

    monkeypatch.setattr(agent_run, "run_tool", boom)
    client = FakeClient([tool_reply("get_personal_words"), text_reply(GOOD)])
    go(ctx, client)
    result = client.calls[1]["messages"][2]["content"][0]
    assert result["is_error"] is True and "db down" in result["content"]


def test_confidence_is_clamped(ctx):
    r = go(ctx, FakeClient([text_reply({**GOOD, "confidence": 1.7})]))
    assert r.confidence == 1.0


@pytest.mark.parametrize("reply", [text_reply("not json"), text_reply({"sentence": "x"}), text_reply({**GOOD, "language": "fr"}), NS(stop_reason="refusal", content=[])])
def test_bad_answers_raise_agent_error(ctx, reply):
    with pytest.raises(AgentError):
        go(ctx, FakeClient([reply]))
