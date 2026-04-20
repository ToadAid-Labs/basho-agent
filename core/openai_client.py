import os
import json
from typing import Any
from dotenv import load_dotenv

load_dotenv()

class OpenAIClient:
    """Wrapper around the OpenAI API for ChatGPT."""

    def __init__(self, model: str | None = None):
        import openai
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY not set.")
        self.client = openai.OpenAI(api_key=api_key)
        self.model = model or os.getenv("OPENAI_MODEL", "gpt-5.4-mini")

    def create_message(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        system_prompt: str | None = None,
        max_tokens: int = 4096,
    ) -> Any:
        # Convert Anthropic messages to OpenAI format
        api_messages = []
        if system_prompt:
            api_messages.append({"role": "system", "content": system_prompt})
            
        for msg in messages:
            role = msg.get("role")
            content = msg.get("content")
            
            if isinstance(content, list):
                # Flatten tool use / tool results into OpenAI format
                text_parts = []
                tool_calls = []
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "tool_result":
                        api_messages.append({
                            "role": "tool",
                            "tool_call_id": block.get("tool_use_id"),
                            "content": block.get("content", "")
                        })
                    elif isinstance(block, dict) and block.get("type") == "tool_use":
                        tool_calls.append({
                            "id": block.get("id"),
                            "type": "function",
                            "function": {
                                "name": block.get("name"),
                                "arguments": json.dumps(block.get("input", {})),
                            },
                        })
                    elif isinstance(block, dict) and block.get("type") == "text":
                        text_parts.append(block.get("text", ""))
                    elif isinstance(block, str):
                        text_parts.append(block)
                if tool_calls:
                    api_messages.append({
                        "role": role,
                        "content": "\n".join(text_parts) if text_parts else None,
                        "tool_calls": tool_calls,
                    })
                elif text_parts:
                    api_messages.append({"role": role, "content": "\n".join(text_parts)})
            else:
                api_messages.append({"role": role, "content": content})

        api_tools = []
        for t in tools:
            api_tools.append({
                "type": "function",
                "function": {
                    "name": t["name"],
                    "description": t.get("description", ""),
                    "parameters": t.get("input_schema", {}),
                }
            })

        kwargs = {
            "model": self.model,
            "messages": api_messages,
            "max_tokens": max_tokens,
        }
        if api_tools:
            kwargs["tools"] = api_tools

        response = self.client.chat.completions.create(**kwargs)
        return OpenAIResponse(response)

class OpenAIResponse:
    def __init__(self, response):
        choice = response.choices[0]
        msg = choice.message
        
        self.content = []
        if msg.content:
            self.content.append(TextBlock(msg.content))
            
        if msg.tool_calls:
            self.stop_reason = "tool_use"
            for tc in msg.tool_calls:
                args = json.loads(tc.function.arguments)
                self.content.append(ToolUseBlock(tc.id, tc.function.name, args))
        else:
            self.stop_reason = choice.finish_reason

class TextBlock:
    type = "text"
    def __init__(self, text):
        self.text = text

class ToolUseBlock:
    type = "tool_use"
    def __init__(self, id, name, input_args):
        self.id = id
        self.name = name
        self.input = input_args
        
