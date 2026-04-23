from types import SimpleNamespace

from core import agent as agent_module
from core.agent import Agent
from core.agent import (
    _build_provider_messages,
    _format_direct_tool_response,
    _should_return_gemini_tool_directly,
)
from core.provider import ModelProvider


def test_build_provider_messages_caps_history_without_deleting(monkeypatch):
    monkeypatch.setenv("AGENT_MAX_PROVIDER_MESSAGES", "3")
    monkeypatch.setenv("AGENT_MAX_PROVIDER_CHARS", "100000")
    messages = [{"role": "user", "content": f"message {i}"} for i in range(6)]

    provider_messages = _build_provider_messages(messages)

    assert provider_messages == messages[-3:]
    assert len(messages) == 6


def test_build_provider_messages_drops_leading_orphan_tool_results(monkeypatch):
    monkeypatch.setenv("AGENT_MAX_PROVIDER_MESSAGES", "2")
    monkeypatch.setenv("AGENT_MAX_PROVIDER_CHARS", "100000")
    messages = [
        {"role": "assistant", "content": [{"type": "text", "text": "older"}]},
        {
            "role": "user",
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": "old",
                    "name": "check_price",
                    "content": "old result",
                }
            ],
        },
        {"role": "user", "content": "latest"},
    ]

    assert _build_provider_messages(messages) == [messages[-1]]


def test_build_provider_messages_prepends_summary_inside_char_budget(monkeypatch):
    monkeypatch.setenv("AGENT_MAX_PROVIDER_MESSAGES", "2")
    monkeypatch.setenv("AGENT_MAX_PROVIDER_CHARS", "100000")
    messages = [
        {"role": "user", "content": "old"},
        {"role": "assistant", "content": "middle"},
        {"role": "user", "content": "latest"},
    ]

    provider_messages = _build_provider_messages(messages, latest_summary="User is tracking ETH.")

    assert provider_messages[0]["role"] == "user"
    assert "User is tracking ETH." in provider_messages[0]["content"]
    assert provider_messages[1:] == messages[-2:]


def test_unsigned_gemini_tool_calls_return_directly():
    assert _should_return_gemini_tool_directly(ModelProvider.GEMINI, None)
    assert not _should_return_gemini_tool_directly(ModelProvider.GEMINI, "signature")
    assert not _should_return_gemini_tool_directly(ModelProvider.OLLAMA, None)


def test_format_direct_tool_response_includes_intro_and_results():
    response = _format_direct_tool_response(
        "Checking ETH.",
        [{"name": "check_price", "content": "ETH price: $1,234"}],
    )

    assert response == "Checking ETH.\n\nTool result from check_price:\nETH price: $1,234"


def test_agent_stops_identical_paper_trade_price_retry(monkeypatch):
    class FakeClient:
        model = "fake"

        def __init__(self):
            self.calls = 0

        def create_message(self, **kwargs):
            self.calls += 1
            return SimpleNamespace(
                content=[
                    SimpleNamespace(
                        type="tool_use",
                        name="execute_paper_trade",
                        input={"user_id": 1, "symbol": "TOBY", "side": "buy", "amount": 100.0},
                        id=f"tool-{self.calls}",
                    )
                ]
            )

    fake_client = FakeClient()
    executed = []

    monkeypatch.setattr(agent_module, "create_client", lambda provider: fake_client)
    monkeypatch.setattr(agent_module, "get_tool_definitions", lambda: [])
    monkeypatch.setattr(agent_module, "latest_summary", lambda sid: None)
    monkeypatch.setattr(agent_module, "save_session_for_provider", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        agent_module,
        "execute_tool",
        lambda name, raw_input: executed.append((name, raw_input))
        or "Cannot get current price for TOBY. Trade aborted.",
    )

    agent = Agent(provider=ModelProvider.ANTHROPIC, sid="test", history=[])

    response = agent.chat("buy TOBY")

    assert "retry the same unresolved price request" in response
    assert executed == [
        (
            "execute_paper_trade",
            {"user_id": 1, "symbol": "TOBY", "side": "buy", "amount": 100.0},
        )
    ]
