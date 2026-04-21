from core.agent import _build_provider_messages


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
