"""LLM client — OpenAI-compatible API with Ollama support and local fallback."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any

from assistant.config import (
    OLLAMA_BASE_URL,
    OLLAMA_MODEL,
    OPENAI_API_KEY,
    OPENAI_BASE_URL,
    OPENAI_MODEL,
)
from assistant.context.platform_context import build_platform_snapshot, snapshot_to_prompt_text
from assistant.llm.fallback import local_response
from assistant.llm.prompts import INTENT_HINTS, SYSTEM_PROMPT


def _valid_openai_key() -> bool:
    key = (OPENAI_API_KEY or "").strip()
    if len(key) < 20:
        return False
    if "your_api" in key.lower() or key.startswith("sk-placeholder"):
        return False
    return True


def _provider() -> str:
    if _valid_openai_key():
        return "openai"
    try:
        req = urllib.request.Request(f"{OLLAMA_BASE_URL.rstrip('/')}/models")
        with urllib.request.urlopen(req, timeout=2) as resp:
            if resp.status == 200:
                return "ollama"
    except Exception:
        pass
    return "local"


def chat_completion(
    messages: list[dict[str, str]],
    context_snapshot: dict | None = None,
    temperature: float = 0.3,
    max_tokens: int = 2000,
) -> dict[str, Any]:
    """
    Returns {"content": str, "provider": str, "model": str}
    """
    provider = _provider()
    snapshot = context_snapshot or build_platform_snapshot()
    context_text = snapshot_to_prompt_text(snapshot)

    if provider == "local":
        user_msg = messages[-1]["content"] if messages else ""
        return {
            "content": local_response(user_msg, snapshot),
            "provider": "local",
            "model": "rule-based-analyst",
        }

    model = OPENAI_MODEL if provider == "openai" else OLLAMA_MODEL
    base_url = OPENAI_BASE_URL if provider == "openai" else OLLAMA_BASE_URL.rstrip("/")

    system = SYSTEM_PROMPT.format(context=context_text) + "\n" + INTENT_HINTS
    api_messages = [{"role": "system", "content": system}]
    api_messages.extend(messages)

    payload = {
        "model": model,
        "messages": api_messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }

    headers = {"Content-Type": "application/json"}
    if provider == "openai":
        headers["Authorization"] = f"Bearer {OPENAI_API_KEY}"

    req = urllib.request.Request(
        f"{base_url}/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        content = data["choices"][0]["message"]["content"]
        return {"content": content, "provider": provider, "model": model}
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        fallback = local_response(messages[-1]["content"], snapshot)
        return {
            "content": fallback
            + f"\n\n---\n*LLM API error ({e.code}): using local analyst.*\n`{body[:200]}`",
            "provider": "local",
            "model": "fallback-after-error",
        }
    except Exception as e:
        fallback = local_response(messages[-1]["content"], snapshot)
        return {
            "content": fallback + f"\n\n---\n*LLM unavailable: {e}*",
            "provider": "local",
            "model": "fallback-after-error",
        }
