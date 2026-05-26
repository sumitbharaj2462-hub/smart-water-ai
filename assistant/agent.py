"""AquaOps AI agent — orchestrates context, tools, and LLM responses."""

from __future__ import annotations

from assistant.context.platform_context import build_platform_snapshot
from assistant.llm.client import _provider, chat_completion
from assistant.reports.emergency import generate_emergency_report


class WaterAssistantAgent:
    def __init__(self):
        self._snapshot = None

    def refresh_context(self) -> dict:
        self._snapshot = build_platform_snapshot()
        return self._snapshot

    @property
    def snapshot(self) -> dict:
        if self._snapshot is None:
            self.refresh_context()
        return self._snapshot  # type: ignore

    def chat(self, user_message: str, history: list[dict[str, str]] | None = None) -> dict:
        history = history or []
        messages = list(history) + [{"role": "user", "content": user_message}]
        result = chat_completion(messages, context_snapshot=self.snapshot)
        return result

    def provider_info(self) -> str:
        p = _provider()
        if p == "openai":
            return "OpenAI API"
        if p == "ollama":
            return "Ollama (local LLM)"
        return "Local analyst (no API key — set OPENAI_API_KEY for full LLM)"

    def emergency_report(self, title: str = "Water Supply Emergency Assessment") -> str:
        return generate_emergency_report(incident_title=title, save=True)
