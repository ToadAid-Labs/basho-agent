import os
import json
from typing import Any, Generator

import requests
from dotenv import load_dotenv

load_dotenv()


class OllamaClient:
    """Wrapper around the Ollama /api/chat endpoint."""

    def __init__(
        self,
        model: str | None = None,
        base_url: str | None = None,
    ):
        self.base_url = (base_url or os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")).rstrip("/")
        self.model = model or os.getenv("OLLAMA_MODEL", "minimax-m2.7:cloud")
        self.timeout = int(os.getenv("OLLAMA_TIMEOUT_SECONDS", "900"))

    def create_message(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        system_prompt: str | None = None,
        max_tokens: int = 4096,
    ) -> "OllamaResponse":
        """Send a chat request to Ollama and return a normalised response."""
        # Build the API tool format
        api_tools = self._to_api_tools(tools)

        # Inject system prompt as a leading assistant-system message if present
        api_messages = _build_messages(messages, system_prompt)

        payload = {
            "model": self.model,
            "messages": api_messages,
            "stream": False,
            "tools": api_tools,
            "options": {"num_predict": max_tokens},
        }

        try:
            resp = requests.post(
                f"{self.base_url}/api/chat",
                json=payload,
                timeout=self.timeout,
            )
            resp.raise_for_status()
        except requests.RequestException as e:
            raise RuntimeError(f"Ollama request failed: {e}") from e

        data = resp.json()
        return OllamaResponse.from_api(data, api_tools)

    def create_message_stream(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        system_prompt: str | None = None,
        max_tokens: int = 4096,
    ) -> Generator[Any, None, None]:
        """Stream chat messages from Ollama."""
        api_tools = self._to_api_tools(tools)
        api_messages = _build_messages(messages, system_prompt)

        payload = {
            "model": self.model,
            "messages": api_messages,
            "stream": True,
            "tools": api_tools,
            "options": {"num_predict": max_tokens},
        }

        try:
            resp = requests.post(
                f"{self.base_url}/api/chat",
                json=payload,
                timeout=self.timeout,
                stream=True,
            )
            resp.raise_for_status()
        except requests.RequestException as e:
            raise RuntimeError(f"Ollama stream request failed: {e}") from e

        for line in resp.iter_lines():
            if not line:
                continue
            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                continue

            message = data.get("message", {})
            
            # Text fragment
            content = message.get("content", "")
            if content:
                yield TextBlock(text=content)
            
            # Tool calls (usually only at the end or in specific chunks)
            for tc in message.get("tool_calls", []):
                fn = tc.get("function", {})
                args = fn.get("arguments", {})
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except json.JSONDecodeError:
                        args = {"_raw": args}
                
                yield ToolUseBlock(
                    id=tc.get("id", ""),
                    name=fn.get("name", ""),
                    input=args
                )

    @staticmethod
    def _to_api_tools(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Convert Claude-style tool definitions to Ollama function format."""
        result = []
        for t in tools:
            fn = t.get("input_schema", {})
            result.append({
                "type": "function",
                "function": {
                    "name": t["name"],
                    "description": t.get("description", ""),
                    "parameters": fn,
                },
            })
        return result


class OllamaResponse:
    """Normalised response that mirrors the parts of Anthropic's response we use."""

    def __init__(
        self,
        content: list[Any],
        raw: dict[str, Any],
    ):
        self.content = content
        self.raw = raw
        self.stop_reason = raw.get("done_reason", "end_turn")

    @classmethod
    def from_api(cls, data: dict[str, Any], api_tools: list[dict[str, Any]]) -> "OllamaResponse":
        message = data.get("message", {})
        raw = message.get("raw", {}) if isinstance(message.get("raw"), dict) else {}

        content: list[Any] = []

        # Text content
        if message.get("content"):
            content.append(TextBlock(text=message["content"]))

        # Tool calls
        for tc in message.get("tool_calls", []):
            fn = tc.get("function", {})
            name = fn.get("name", "")
            raw_args = fn.get("arguments", {})
            # arguments may be a dict or a JSON string
            if isinstance(raw_args, str):
                try:
                    raw_args = json.loads(raw_args)
                except Exception:  # noqa: BLE001
                    raw_args = {"_raw": raw_args}
            content.append(ToolUseBlock(
                id=tc.get("id", ""),
                name=name,
                input=raw_args,
            ))

        return cls(content=content, raw=data)


class TextBlock:
    type = "text"

    def __init__(self, text: str):
        self.text = text


class ToolUseBlock:
    type = "tool_use"

    def __init__(self, id: str, name: str, input: dict[str, Any]):
        self.id = id
        self.name = name
        self.input = input


def _build_messages(
    messages: list[dict[str, Any]],
    system_prompt: str | None,
) -> list[dict[str, Any]]:
    """Normalise the message list into Ollama format."""
    result: list[dict[str, Any]] = []

    if system_prompt:
        result.append({"role": "system", "content": system_prompt})

    for msg in messages:
        role = msg.get("role", "user")
        if role == "assistant":
            role = "assistant"
        elif role == "tool":
            role = "tool"
        else:
            role = "user"

        content = msg.get("content", "")
        # Handle content blocks (e.g. tool_result)
        if isinstance(content, list):
            # Ollama doesn't support content blocks — flatten to text
            text_parts = []
            for block in content:
                if isinstance(block, dict):
                    if block.get("type") == "tool_result":
                        text_parts.append(block.get("content", ""))
                    else:
                        text_parts.append(str(block))
                else:
                    text_parts.append(str(block))
            content = "\n".join(text_parts)

        result.append({"role": role, "content": content})

    return result
