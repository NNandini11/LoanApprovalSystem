"""Anthropic Claude client wrapper with prompt caching.

The system prompt is sent as a cached block so subsequent loan applications
within the 5-minute cache window reuse it (cheaper, faster).
"""
from __future__ import annotations

import json
import os
import re
from typing import Optional

from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()

MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-6")
_client: Optional[Anthropic] = None


def _client_singleton() -> Anthropic:
    global _client
    if _client is None:
        _client = Anthropic()
    return _client


def call_claude(
    system_prompt: str,
    user_message: str,
    *,
    max_tokens: int = 1024,
    temperature: float = 0.2,
) -> str:
    """Call Claude with a cached system prompt. Returns the assistant text."""
    client = _client_singleton()
    response = client.messages.create(
        model=MODEL,
        max_tokens=max_tokens,
        temperature=temperature,
        system=[
            {
                "type": "text",
                "text": system_prompt,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[{"role": "user", "content": user_message}],
    )
    return "".join(
        block.text for block in response.content if getattr(block, "type", None) == "text"
    )


def extract_json(text: str) -> dict:
    """Pull the first JSON object out of an LLM response (handles ```json fences).

    Uses a string-aware brace counter so trailing prose, a second object, or
    a code-fence-then-prose pattern all still resolve to the first valid object.
    """
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fenced:
        return json.loads(fenced.group(1))

    start = text.find("{")
    while start != -1:
        depth = 0
        in_string = False
        escape = False
        for i in range(start, len(text)):
            ch = text[i]
            if escape:
                escape = False
                continue
            if ch == "\\" and in_string:
                escape = True
                continue
            if ch == '"':
                in_string = not in_string
                continue
            if in_string:
                continue
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    candidate = text[start : i + 1]
                    try:
                        return json.loads(candidate)
                    except json.JSONDecodeError:
                        break
        start = text.find("{", start + 1)

    raise ValueError(f"No JSON object found in LLM output: {text!r}")
