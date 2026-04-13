"""
Thin async wrapper around the official Anthropic SDK.
Replaces the private `emergentintegrations` package (not on PyPI) for Vercel/CI installs.
"""
from __future__ import annotations

from dataclasses import dataclass

import anthropic

DEFAULT_CLAUDE_MODEL = "claude-opus-4-5-20251101"


@dataclass
class UserMessage:
    text: str


class ClaudeChat:
    """API-compatible with previous LlmChat usage: with_model + send_message."""

    def __init__(
        self,
        api_key: str,
        session_id: str,
        system_message: str,
        model: str = DEFAULT_CLAUDE_MODEL,
    ):
        self._session_id = session_id
        self._system = system_message
        self._model = model
        self._client = anthropic.AsyncAnthropic(api_key=api_key)

    def with_model(self, provider: str, model: str) -> "ClaudeChat":
        if provider != "anthropic":
            raise ValueError("Only anthropic provider is supported")
        self._model = model
        return self

    async def send_message(self, msg: UserMessage, temperature: float | None = None) -> str:
        kwargs = {
            "model": self._model,
            "max_tokens": 16384,
            "system": self._system,
            "messages": [{"role": "user", "content": msg.text}],
        }
        if temperature is not None:
            kwargs["temperature"] = max(0.0, min(1.0, float(temperature)))
        message = await self._client.messages.create(**kwargs)
        parts: list[str] = []
        for block in message.content:
            btype = getattr(block, "type", None)
            if btype == "text":
                parts.append(getattr(block, "text", "") or "")
            elif isinstance(block, dict) and block.get("type") == "text":
                parts.append(block.get("text", ""))
        return "".join(parts)


def get_claude_chat(session_id: str, system_msg: str, model: str = DEFAULT_CLAUDE_MODEL) -> ClaudeChat:
    import os

    key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not key:
        raise ValueError("ANTHROPIC_API_KEY not configured in .env")
    return ClaudeChat(api_key=key, session_id=session_id, system_message=system_msg, model=model)
