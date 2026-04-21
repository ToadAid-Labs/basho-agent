import base64
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.gemini_client import GeminiClient, GeminiResponse, _function_call_id


class EmptyContent:
    parts = []


class EmptyCandidate:
    content = EmptyContent()
    finish_reason = 12


class EmptyGeminiResponse:
    candidates = [EmptyCandidate()]
    prompt_feedback = None


class FunctionCallPart:
    def __init__(self, name="web_search", args=None, thought_signature=None, call_id="call-1"):
        self.function_call = type(
            "FunctionCall",
            (),
            {
                "name": name,
                "args": args or {"query": "toby base"},
                "thought_signature": None,
                "id": call_id,
            },
        )()
        self.thought_signature = thought_signature


class FunctionCallCandidate:
    def __init__(self, part):
        self.content = type("Content", (), {"parts": [part]})()


class FunctionCallGeminiResponse:
    def __init__(self, part):
        self.candidates = [FunctionCallCandidate(part)]
        self.prompt_feedback = None


def test_gemini_response_handles_empty_candidate_parts():
    response = GeminiResponse(EmptyGeminiResponse())

    assert response.stop_reason == "12"
    assert response.content[0].type == "text"
    assert "Gemini returned no text" in response.content[0].text
    assert "finish_reason=12" in response.content[0].text


def test_gemini_response_preserves_thought_signature_as_json_safe_text():
    response = GeminiResponse(FunctionCallGeminiResponse(FunctionCallPart(thought_signature=b"sig-bytes")))

    assert response.content[0].type == "tool_use"
    assert response.content[0].thought_signature == base64.b64encode(b"sig-bytes").decode("ascii")


def test_gemini_content_builder_restores_thought_signature_bytes():
    client = GeminiClient.__new__(GeminiClient)
    messages = [
        {
            "role": "assistant",
            "content": [
                {
                    "type": "tool_use",
                    "name": "web_search",
                    "input": {"query": "toby base"},
                    "thought_signature": base64.b64encode(b"sig-bytes").decode("ascii"),
                    "id": "call-1",
                }
            ],
        }
    ]

    contents = client._build_contents_new(messages)
    part = contents[0].parts[0]

    assert part.thought_signature == b"sig-bytes"
    assert part.function_call.name == "web_search"


def test_legacy_content_builder_puts_thought_signature_on_part():
    client = GeminiClient.__new__(GeminiClient)
    messages = [
        {
            "role": "assistant",
            "content": [
                {
                    "type": "tool_use",
                    "name": "web_search",
                    "input": {"query": "toby base"},
                    "thought_signature": base64.b64encode(b"sig-bytes").decode("ascii"),
                    "id": "call-1",
                }
            ],
        }
    ]

    contents = client._build_contents_legacy(messages, system_prompt=None)

    assert contents[0]["parts"][0]["thought_signature"] == b"sig-bytes"
    assert "thought_signature" not in contents[0]["parts"][0]["function_call"]


def test_function_call_id_does_not_use_raw_binary_signature():
    raw_signature = b"\xbe\x00sig"

    assert _function_call_id({"id": "call-1"}, raw_signature) == "call-1"
    assert _function_call_id({}, raw_signature) == base64.b64encode(raw_signature).decode("ascii")
