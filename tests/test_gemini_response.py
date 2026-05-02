import base64
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.agent import _should_return_gemini_tool_directly
from core.gemini_client import GeminiClient, GeminiResponse, _function_call_id, _json_safe_value
from core.provider import ModelProvider


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


class RepeatedCompositeStub:
    def __iter__(self):
        return iter([{"symbol": "BTC"}, {"symbol": "ETH"}])


class LegacyProtoStub:
    class FunctionCall:
        def __init__(self, name, args):
            self.name = name
            self.args = args

        def __contains__(self, key):
            return hasattr(self, key)

    class FunctionResponse:
        def __init__(self, name, response):
            self.name = name
            self.response = response

    class Part:
        def __init__(self, **kwargs):
            self.thought_signature = None
            for key, value in kwargs.items():
                setattr(self, key, value)

        def __getitem__(self, key):
            return getattr(self, key)


def legacy_test_client():
    client = GeminiClient.__new__(GeminiClient)
    client.proto = LegacyProtoStub
    return client


def test_gemini_response_handles_empty_candidate_parts():
    response = GeminiResponse(EmptyGeminiResponse())

    assert response.stop_reason == "12"
    assert response.content[0].type == "text"
    assert "Gemini returned no text" in response.content[0].text
    assert "finish_reason=12" in response.content[0].text


def test_gemini_response_preserves_thought_signature_as_json_safe_text():
    response = GeminiResponse(FunctionCallGeminiResponse(FunctionCallPart(thought_signature=b"sig-bytes")))

    assert response.content[0].type == "tool_use"
    assert response.content[0].id == "call-1"
    assert response.content[0].thought_signature == base64.b64encode(b"sig-bytes").decode("ascii")


def test_gemini_response_does_not_treat_function_call_id_as_signature():
    response = GeminiResponse(FunctionCallGeminiResponse(FunctionCallPart(call_id="m5ag5amp")))

    assert response.content[0].type == "tool_use"
    assert response.content[0].id == "m5ag5amp"
    assert response.content[0].thought_signature is None


def test_gemini_response_tool_args_are_json_safe():
    response = GeminiResponse(
        FunctionCallGeminiResponse(
            FunctionCallPart(args={"symbols": RepeatedCompositeStub(), "chain": "base"})
        )
    )

    assert response.content[0].input == {
        "symbols": [{"symbol": "BTC"}, {"symbol": "ETH"}],
        "chain": "base",
    }


def test_json_safe_value_handles_repeated_composite_like_values():
    assert _json_safe_value({"items": RepeatedCompositeStub()}) == {
        "items": [{"symbol": "BTC"}, {"symbol": "ETH"}]
    }


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


def test_gemini_content_builder_collapses_unsigned_tool_calls_to_text():
    client = GeminiClient.__new__(GeminiClient)
    messages = [
        {
            "role": "assistant",
            "content": [
                {
                    "type": "tool_use",
                    "name": "web_search",
                    "input": {"query": "BTC"},
                    "thought_signature": None,
                    "id": "call-1",
                }
            ],
        },
        {
            "role": "user",
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": "call-1",
                    "name": "web_search",
                    "content": "No results found.",
                }
            ],
        },
    ]

    contents = client._build_contents_new(messages)

    assert contents[0].parts[0].function_call is None
    assert "Tool call recorded without Gemini thought signature" in contents[0].parts[0].text
    assert contents[1].parts[0].function_response is None
    assert "Tool result from web_search" in contents[1].parts[0].text


def test_legacy_content_builder_puts_thought_signature_on_part():
    client = legacy_test_client()
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


def test_legacy_content_builder_collapses_unsigned_tool_calls_to_text():
    client = legacy_test_client()
    messages = [
        {
            "role": "assistant",
            "content": [
                {
                    "type": "tool_use",
                    "name": "web_search",
                    "input": {"query": "BTC"},
                    "thought_signature": None,
                    "id": "call-1",
                }
            ],
        },
        {
            "role": "user",
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": "call-1",
                    "name": "web_search",
                    "content": "No results found.",
                }
            ],
        },
    ]

    contents = client._build_contents_legacy(messages, system_prompt=None)

    assert "Tool call recorded without Gemini thought signature" in contents[0]["parts"][0]["text"]
    assert "Tool result from web_search" in contents[1]["parts"][0]["text"]


def test_function_call_id_does_not_use_raw_binary_signature():
    raw_signature = b"\xbe\x00sig"

    assert _function_call_id({"id": "call-1"}, raw_signature) == "call-1"
    assert _function_call_id({}, raw_signature) == base64.b64encode(raw_signature).decode("ascii")


def test_gemini_tool_results_are_not_returned_directly():
    assert _should_return_gemini_tool_directly(ModelProvider.GEMINI, None) is False


def test_gemini_client_reloads_oauth_when_token_file_changes(monkeypatch):
    client = GeminiClient.__new__(GeminiClient)
    client.uses_legacy_oauth_sdk = True
    client.api_key = None
    client.token_path = "/tmp/fake-google-token.json"
    client._token_mtime = 1.0
    reloads = []

    monkeypatch.setattr("core.gemini_client.os.path.getmtime", lambda path: 2.0)
    monkeypatch.setattr(
        client,
        "_configure_legacy_oauth_client",
        lambda: reloads.append(client.token_path),
    )

    assert client._reload_legacy_oauth_if_token_changed() is True
    assert reloads == ["/tmp/fake-google-token.json"]


def test_gemini_client_keeps_oauth_client_when_token_file_unchanged(monkeypatch):
    client = GeminiClient.__new__(GeminiClient)
    client.uses_legacy_oauth_sdk = True
    client.api_key = None
    client.token_path = "/tmp/fake-google-token.json"
    client._token_mtime = 2.0

    monkeypatch.setattr("core.gemini_client.os.path.getmtime", lambda path: 2.0)
    monkeypatch.setattr(
        client,
        "_configure_legacy_oauth_client",
        lambda: (_ for _ in ()).throw(AssertionError("should not reload")),
    )

    assert client._reload_legacy_oauth_if_token_changed() is False


def test_gemini_client_persists_refreshed_oauth_credentials(tmp_path):
    token_path = tmp_path / "google-token.json"
    token_path.write_text("{}")

    client = GeminiClient.__new__(GeminiClient)
    client.token_path = str(token_path)
    client._token_mtime = None

    class FakeCreds:
        def to_json(self):
            return json.dumps({"access_token": "new-access", "refresh_token": "new-refresh"})

    client._persist_legacy_oauth_credentials(FakeCreds())

    saved = json.loads(token_path.read_text())
    assert saved["access_token"] == "new-access"
    assert saved["refresh_token"] == "new-refresh"
    assert client._token_mtime == token_path.stat().st_mtime


def test_gemini_client_refreshes_and_persists_oauth_credentials(monkeypatch):
    client = GeminiClient.__new__(GeminiClient)
    client.uses_legacy_oauth_sdk = True
    client.api_key = None

    class FakeCreds:
        valid = False
        expired = True

        def refresh(self, request):
            self.valid = True
            self.expired = False

    creds = FakeCreds()
    persisted = []
    client.creds = creds
    client._persist_legacy_oauth_credentials = lambda refreshed_creds: persisted.append(refreshed_creds)

    class FakeRefreshError(Exception):
        pass

    monkeypatch.setitem(
        sys.modules,
        "google.auth.exceptions",
        type("GoogleAuthExceptions", (), {"RefreshError": FakeRefreshError}),
    )
    monkeypatch.setitem(
        sys.modules,
        "google.auth.transport.requests",
        type("GoogleAuthRequests", (), {"Request": lambda: object()}),
    )

    client._ensure_legacy_oauth_fresh()

    assert persisted == [creds]
    assert creds.valid is True
    assert creds.expired is False
