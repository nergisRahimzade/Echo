"""The agent loop: read the guesses, look things up if needed, decide on ONE sentence.

Claude (Sonnet) gets the Whisper candidates, sound matches and context, may call memory
tools (at most MAX_TOOL_ROUNDS rounds), and must answer with JSON matching OUTPUT_SCHEMA
(enforced by structured outputs, then validated again with Pydantic).
"""

import asyncio
import json
import logging
import time
from typing import Literal

import anthropic
from pydantic import BaseModel, Field, ValidationError, field_validator

from app.agent.prompt import OUTPUT_SCHEMA, SYSTEM_PROMPT, build_user_message
from app.agent.tools import TOOL_DEFINITIONS, ToolContext, run_tool
from app.config import get_settings

logger = logging.getLogger("echo.agent")

MAX_TOOL_ROUNDS = 3
# Server-side fallback: if a safety filter declines the request, the API reruns it on a
# suitable fallback model inside the same call.
FALLBACK_BETA = "server-side-fallback-2026-07-01"


class AgentResult(BaseModel):
    sentence: str
    confidence: float = Field(ge=0.0, le=1.0)
    language: Literal["tr", "en", "mixed"]
    reason: str
    tool_calls: list[str] = Field(default_factory=list)
    seconds: float = 0.0

    @field_validator("sentence", "reason")
    @classmethod
    def strip(cls, v: str) -> str:
        return v.strip()

    @field_validator("confidence", mode="before")
    @classmethod
    def clamp(cls, v):
        return min(1.0, max(0.0, float(v)))


class AgentError(RuntimeError):
    """Claude could not be reached or did not produce a usable answer."""


_client: anthropic.AsyncAnthropic | None = None


def get_client() -> anthropic.AsyncAnthropic:
    global _client
    if _client is None:
        _client = anthropic.AsyncAnthropic(api_key=get_settings().anthropic_api_key, max_retries=2, timeout=20.0)
    return _client


def _final_text(content) -> str:
    return next((b.text for b in content if getattr(b, "type", None) == "text"), "")


async def interpret(
    ctx: ToolContext,
    candidates: list[str],
    sound_matches: list[tuple[str, float]],
    language_hint: str | None = None,
    personal_words: list[tuple[str, str]] | None = None,
    recent_turns: list[tuple[str, str]] | None = None,
    rejected: list[str] | None = None,
    client: anthropic.AsyncAnthropic | None = None,
) -> AgentResult:
    """Ask the agent for the one sentence the user meant."""
    s = get_settings()
    client = client or get_client()
    started = time.perf_counter()
    messages: list[dict] = [
        {
            "role": "user",
            "content": build_user_message(candidates, sound_matches, language_hint, personal_words, recent_turns, rejected),
        }
    ]
    tool_calls: list[str] = []

    for round_no in range(MAX_TOOL_ROUNDS + 1):
        last_round = round_no == MAX_TOOL_ROUNDS
        try:
            response = await client.beta.messages.create(
                model=s.agent_model,
                max_tokens=4000,
                system=[{"type": "text", "text": SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}],
                tools=TOOL_DEFINITIONS,
                # After the last allowed tool round, tools are switched off: answer now.
                tool_choice={"type": "none"} if last_round else {"type": "auto"},
                output_config={"effort": s.agent_effort, "format": {"type": "json_schema", "schema": OUTPUT_SCHEMA}},
                betas=[FALLBACK_BETA],
                fallbacks="default",
                messages=messages,
            )
        except anthropic.APIConnectionError as exc:
            raise AgentError(f"Cannot reach Claude: {exc}") from exc
        except anthropic.RateLimitError as exc:
            raise AgentError("Claude rate limit reached") from exc
        except anthropic.APIStatusError as exc:
            raise AgentError(f"Claude error {exc.status_code}: {exc.message}") from exc

        if response.stop_reason == "refusal":
            raise AgentError("Claude declined this request")

        if response.stop_reason == "tool_use" and not last_round:
            uses = [b for b in response.content if b.type == "tool_use"]
            messages.append({"role": "assistant", "content": response.content})
            outputs = await asyncio.gather(*(run_tool(ctx, u.name, u.input) for u in uses), return_exceptions=True)
            results = []
            for use, out in zip(uses, outputs):
                tool_calls.append(use.name)
                if isinstance(out, Exception):
                    results.append({"type": "tool_result", "tool_use_id": use.id, "content": f"Error: {out}", "is_error": True})
                else:
                    results.append({"type": "tool_result", "tool_use_id": use.id, "content": out})
            # All results go back in ONE user message.
            messages.append({"role": "user", "content": results})
            continue

        text = _final_text(response.content)
        try:
            data = json.loads(text)
            return AgentResult(**data, tool_calls=tool_calls, seconds=round(time.perf_counter() - started, 2))
        except (json.JSONDecodeError, ValidationError, TypeError) as exc:
            raise AgentError(f"Agent returned invalid JSON ({response.stop_reason}): {text[:200]}") from exc

    raise AgentError("Agent did not finish within the tool-round limit")
