import os
from typing import Any

from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()


class ClaudeClient:
    """Thin wrapper around the Anthropic API client."""

    def __init__(self, model: str = "claude-opus-4-6"):
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY not set. Check your .env file.")
        self.client = Anthropic(api_key=api_key)
        self.model = model

    def create_message(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        system_prompt: str | None = None,
        max_tokens: int = 4096,
    ) -> Any:
        """Send a message to Claude and return the response."""
        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens,
        }
        if tools:
            kwargs["tools"] = tools
        if system_prompt:
            kwargs["system"] = system_prompt

        return self.client.messages.create(**kwargs)
