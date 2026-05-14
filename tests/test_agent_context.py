from types import SimpleNamespace

from core import agent as agent_module
from core.agent import Agent, _telegram_tool_guard_result, _telegram_tool_repeat_guard
from core.agent import (
    _build_provider_messages,
    _build_request_tool_plan,
    _compact_telegram_history,
    _format_direct_tool_response,
    _secret_request_redirect,
    _tool_budget_guard_result,
    _tool_plan_guard_message,
    _should_disable_tools,
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
    assert not _should_return_gemini_tool_directly(ModelProvider.GEMINI, None)
    assert not _should_return_gemini_tool_directly(ModelProvider.GEMINI, "signature")
    assert not _should_return_gemini_tool_directly(ModelProvider.OLLAMA, None)


def test_compact_telegram_history_drops_prior_tool_transcripts():
    compacted = _compact_telegram_history(
        [
            {"role": "user", "content": "give me a market report"},
            {
                "role": "assistant",
                "content": [
                    {"type": "text", "text": "Checking BTC and ETH."},
                    {"type": "tool_use", "name": "web_search", "input": {"query": "btc news"}},
                ],
            },
            {
                "role": "user",
                "content": [
                    {"type": "tool_result", "name": "web_search", "content": "result payload"},
                ],
            },
            {
                "role": "assistant",
                "content": [
                    {"type": "text", "text": "BTC looks firm."},
                ],
            },
        ]
    )

    assert compacted == [
        {"role": "user", "content": "give me a market report"},
        {"role": "assistant", "content": "Checking BTC and ETH.\n\nBTC looks firm."},
    ]


def test_format_direct_tool_response_includes_intro_and_results():
    response = _format_direct_tool_response(
        "Checking ETH.",
        [{"name": "check_price", "content": "ETH price: $1,234"}],
    )

    assert response == "Checking ETH.\n\nTool result from check_price:\nETH price: $1,234"


def test_no_tools_prompt_disables_tool_definitions(monkeypatch):
    class FakeClient:
        model = "fake"

        def __init__(self):
            self.tool_args = []

        def create_message(self, **kwargs):
            self.tool_args.append(kwargs["tools"])
            return SimpleNamespace(content=[SimpleNamespace(type="text", text="2 + 2 = 4.")])

    fake_client = FakeClient()

    monkeypatch.setattr(agent_module, "create_client", lambda provider: fake_client)
    monkeypatch.setattr(agent_module, "get_tool_definitions", lambda: [{"name": "execute_paper_trade"}])
    monkeypatch.setattr(agent_module, "latest_summary", lambda sid: None)
    monkeypatch.setattr(agent_module, "save_session_for_provider", lambda *args, **kwargs: None)

    agent = Agent(provider=ModelProvider.ANTHROPIC, sid="test", history=[])

    response = agent.chat("No tools for this one. Reply in one short sentence: what is 2 + 2?")

    assert _should_disable_tools("No tools for this one.")
    assert response == "2 + 2 = 4."
    assert fake_client.tool_args == [[]]


def test_secret_request_redirect_blocks_wallet_credentials_in_chat():
    response = _secret_request_redirect("My wallet password is hunter2. Use it for the swap.")

    assert response is not None
    assert "Do not send wallet passwords" in response
    assert "secure local TWAK flow" in response


def test_request_tool_plan_prefers_direct_tracked_balance_for_degen_position():
    plan = _build_request_tool_plan("where is my DEGEN?")

    assert plan["mode"] == "tracked_token_position"
    assert plan["stages"][0] == {"get_tracked_token_balance"}


def test_request_tool_plan_prefers_compact_reentry_flow_for_degen_watch_request():
    plan = _build_request_tool_plan("continue to look for opportunity or watch DEGEN price to come down then buy back in")

    assert plan["mode"] == "tracked_token_reentry_watch"
    assert plan["stages"][0] == {"trust_get_token_price"}
    assert plan["stages"][1] == {"trade_decision_engine", "get_swing_setup"}


def test_tool_plan_guard_defers_unrelated_scan_for_sell_remaining():
    plan = _build_request_tool_plan("sell remaining DEGEN")

    message = _tool_plan_guard_message(plan, "check_onchain_risk", tool_calls_executed=0)

    assert message is not None
    assert "deferred `check_onchain_risk`" in message
    assert "direct tracked-token balance and execution prep" in message


def test_tool_budget_guard_result_describes_partial_results():
    plan = _build_request_tool_plan("check my wallet")
    cached = {
        '{"input": {}, "name": "get_wallet_balance"}': "wallet summary",
        '{"input": {"symbol": "DEGEN"}, "name": "get_tracked_token_balance"}': "degen balance",
    }

    message = _tool_budget_guard_result(plan, cached, "list_alerts")

    assert "Completed first: get_wallet_balance, get_tracked_token_balance" in message
    assert "Deferred:" in message
    assert "alerts" in message or "list_alerts" in message


def test_agent_stops_interleaved_paper_trade_price_retry_before_budget(monkeypatch):
    class FakeClient:
        model = "fake"
        sequence = [
            ("execute_paper_trade", {"user_id": 1, "symbol": "TOBY", "side": "buy", "amount": 100.0}),
            ("trust_get_token_price", {"token_symbol": "TOBY", "chain": "base"}),
            ("execute_paper_trade", {"user_id": 1, "symbol": "TOBY", "side": "buy", "amount": 100.0}),
        ]

        def __init__(self):
            self.calls = 0

        def create_message(self, **kwargs):
            tool_name, tool_input = self.sequence[self.calls]
            self.calls += 1
            return SimpleNamespace(
                content=[
                    SimpleNamespace(
                        type="tool_use",
                        name=tool_name,
                        input=tool_input,
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
    monkeypatch.setenv("AGENT_MAX_TOOL_CALLS", "2")

    def fake_execute_tool(name, raw_input):
        executed.append((name, raw_input))
        if name == "execute_paper_trade":
            return "Cannot get current price for TOBY. Trade aborted."
        return '{"priceUsd": "0.01"}'

    monkeypatch.setattr(agent_module, "execute_tool", fake_execute_tool)

    agent = Agent(provider=ModelProvider.ANTHROPIC, sid="test", history=[])

    response = agent.chat("buy TOBY")

    assert "retry the same unresolved price request" in response
    assert executed == [
        (
            "execute_paper_trade",
            {"user_id": 1, "symbol": "TOBY", "side": "buy", "amount": 100.0},
        ),
        ("trust_get_token_price", {"token_symbol": "TOBY", "chain": "base"}),
    ]


def test_agent_stops_duplicate_paper_trade_after_success_before_budget(monkeypatch):
    class FakeClient:
        model = "fake"
        sequence = [
            (
                "execute_paper_trade",
                {"user_id": 1, "symbol": "TOBY", "side": "buy", "amount": 100.0, "entry_price": 0.01},
            ),
            ("trust_search_token", {"query": "TOBY"}),
            (
                "execute_paper_trade",
                {"user_id": 1, "symbol": "TOBY", "side": "buy", "amount": 100.0, "entry_price": 0.01},
            ),
        ]

        def __init__(self):
            self.calls = 0

        def create_message(self, **kwargs):
            tool_name, tool_input = self.sequence[self.calls]
            self.calls += 1
            return SimpleNamespace(
                content=[
                    SimpleNamespace(
                        type="tool_use",
                        name=tool_name,
                        input=tool_input,
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
    monkeypatch.setenv("AGENT_MAX_TOOL_CALLS", "2")

    def fake_execute_tool(name, raw_input):
        executed.append((name, raw_input))
        if name == "execute_paper_trade":
            return "✅ Paper BUY Executed\n   Symbol: TOBY"
        return '{"symbol": "TOBY"}'

    monkeypatch.setattr(agent_module, "execute_tool", fake_execute_tool)

    agent = Agent(provider=ModelProvider.ANTHROPIC, sid="test", history=[])

    response = agent.chat("buy TOBY")

    assert "same paper trade was already attempted" in response
    assert executed == [
        (
            "execute_paper_trade",
            {"user_id": 1, "symbol": "TOBY", "side": "buy", "amount": 100.0, "entry_price": 0.01},
        ),
        ("trust_search_token", {"query": "TOBY"}),
    ]


def test_agent_reuses_duplicate_tool_results_without_spending_budget(monkeypatch):
    class FakeClient:
        model = "fake"
        sequence = [
            ("get_pro_indicators", {"symbol": "BTC"}),
            ("get_pro_indicators", {"symbol": "BTC"}),
            ("get_multi_timeframe_signal", {"symbol": "BTC"}),
            ("get_multi_timeframe_signal", {"symbol": "BTC"}),
            None,
        ]

        def __init__(self):
            self.calls = 0

        def create_message(self, **kwargs):
            item = self.sequence[self.calls]
            self.calls += 1
            if item is None:
                return SimpleNamespace(content=[SimpleNamespace(type="text", text="Analysis complete.")])
            tool_name, tool_input = item
            return SimpleNamespace(
                content=[
                    SimpleNamespace(
                        type="tool_use",
                        name=tool_name,
                        input=tool_input,
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
    monkeypatch.setenv("AGENT_MAX_TOOL_CALLS", "2")

    def fake_execute_tool(name, raw_input):
        executed.append((name, raw_input))
        return f"result for {name} {raw_input['symbol']}"

    monkeypatch.setattr(agent_module, "execute_tool", fake_execute_tool)

    agent = Agent(provider=ModelProvider.ANTHROPIC, sid="test", history=[])

    response = agent.chat("analyze BTC")

    assert response == "Analysis complete."
    assert executed == [
        ("get_pro_indicators", {"symbol": "BTC"}),
        ("get_multi_timeframe_signal", {"symbol": "BTC"}),
    ]


def test_broad_wallet_status_returns_partial_results_instead_of_hard_stop(monkeypatch):
    class FakeClient:
        model = "fake"

        def __init__(self):
            self.calls = 0
            self.tools_seen = []

        def create_message(self, **kwargs):
            self.tools_seen.append(kwargs["tools"])
            self.calls += 1
            if self.calls == 1:
                return SimpleNamespace(
                    content=[
                        SimpleNamespace(type="tool_use", name="get_wallet_balance", input={}, id="tool-1")
                    ]
                )
            if self.calls == 2:
                return SimpleNamespace(
                    content=[
                        SimpleNamespace(
                            type="text",
                            text="I checked the most important pieces first: wallet summary. I deferred price lookup, recent history, alerts, and risk/market scan to avoid over-running the tool budget.",
                        )
                    ]
                )
            raise AssertionError("Unexpected extra LLM call")

    fake_client = FakeClient()

    monkeypatch.setattr(agent_module, "create_client", lambda provider: fake_client)
    monkeypatch.setattr(agent_module, "get_tool_definitions", lambda: [{"name": "get_wallet_balance"}])
    monkeypatch.setattr(agent_module, "latest_summary", lambda sid: None)
    monkeypatch.setattr(agent_module, "save_session_for_provider", lambda *args, **kwargs: None)
    monkeypatch.setattr(agent_module, "execute_tool", lambda name, raw_input: "wallet summary")
    monkeypatch.setenv("AGENT_MAX_TOOL_CALLS", "1")

    agent = Agent(provider=ModelProvider.ANTHROPIC, sid="test", history=[])

    response = agent.chat("analyze BTC")

    assert "I checked the most important pieces first" in response
    assert "too many tools at once" not in response


def test_agent_returns_partial_results_when_tool_budget_is_exceeded(monkeypatch):
    class FakeClient:
        model = "fake"

        def __init__(self):
            self.calls = 0
            self.tools_seen = []

        def create_message(self, **kwargs):
            self.tools_seen.append(kwargs["tools"])
            self.calls += 1
            if self.calls == 1:
                return SimpleNamespace(
                    content=[SimpleNamespace(type="tool_use", name="get_pro_indicators", input={"symbol": "BTC"}, id="tool-1")]
                )
            if self.calls == 2:
                return SimpleNamespace(
                    content=[SimpleNamespace(type="tool_use", name="get_multi_timeframe_signal", input={"symbol": "BTC"}, id="tool-2")]
                )
            if self.calls == 3:
                return SimpleNamespace(
                    content=[SimpleNamespace(type="tool_use", name="analyze_market_structure", input={"symbol": "BTC"}, id="tool-3")]
                )
            if self.calls == 4:
                return SimpleNamespace(
                    content=[
                        SimpleNamespace(
                            type="text",
                            text="I checked the most important pieces first: indicators and multi-timeframe trend. I deferred market structure to avoid over-running the tool budget.",
                        )
                    ]
                )
            raise AssertionError("Unexpected extra LLM call")

    fake_client = FakeClient()
    executed = []

    monkeypatch.setattr(agent_module, "create_client", lambda provider: fake_client)
    monkeypatch.setattr(
        agent_module,
        "get_tool_definitions",
        lambda: [{"name": "get_pro_indicators"}, {"name": "get_multi_timeframe_signal"}, {"name": "analyze_market_structure"}],
    )
    monkeypatch.setattr(agent_module, "latest_summary", lambda sid: None)
    monkeypatch.setattr(agent_module, "save_session_for_provider", lambda *args, **kwargs: None)
    monkeypatch.setenv("AGENT_MAX_TOOL_CALLS", "2")

    def fake_execute_tool(name, raw_input):
        executed.append((name, raw_input))
        return f"result {name}"

    monkeypatch.setattr(agent_module, "execute_tool", fake_execute_tool)

    agent = Agent(provider=ModelProvider.ANTHROPIC, sid="test", history=[])

    response = agent.chat("analyze BTC")

    assert "I checked the most important pieces first" in response
    assert "too many tools at once" not in response
    assert executed == [
        ("get_pro_indicators", {"symbol": "BTC"}),
        ("get_multi_timeframe_signal", {"symbol": "BTC"}),
    ]
    assert fake_client.tools_seen[-1] == []


def test_degen_position_flow_blocks_full_market_scan_before_direct_balance(monkeypatch):
    class FakeClient:
        model = "fake"

        def __init__(self):
            self.calls = 0

        def create_message(self, **kwargs):
            self.calls += 1
            if self.calls == 1:
                return SimpleNamespace(
                    content=[
                        SimpleNamespace(type="tool_use", name="trust_get_token_price", input={"token_symbol": "DEGEN", "chain": "base"}, id="tool-1")
                    ]
                )
            return SimpleNamespace(
                content=[
                    SimpleNamespace(type="text", text="I checked DEGEN directly first and deferred broader scans.")
                ]
            )

    fake_client = FakeClient()
    executed = []

    monkeypatch.setattr(agent_module, "create_client", lambda provider: fake_client)
    monkeypatch.setattr(agent_module, "get_tool_definitions", lambda: [{"name": "trust_get_token_price"}, {"name": "get_tracked_token_balance"}])
    monkeypatch.setattr(agent_module, "latest_summary", lambda sid: None)
    monkeypatch.setattr(agent_module, "save_session_for_provider", lambda *args, **kwargs: None)
    monkeypatch.setattr(agent_module, "execute_tool", lambda name, raw_input: executed.append((name, raw_input)) or "ok")

    agent = Agent(provider=ModelProvider.ANTHROPIC, sid="test", history=[])

    response = agent.chat("where is my DEGEN?")

    assert response == "I checked DEGEN directly first and deferred broader scans."
    assert executed == []


def test_sell_remaining_degen_does_not_trigger_unrelated_market_scans(monkeypatch):
    class FakeClient:
        model = "fake"
        sequence = [
            ("get_tracked_token_balance", {"symbol": "DEGEN", "chain": "base"}),
            ("trust_get_swap_quote", {"from_token": "DEGEN", "to_token": "ETH", "amount": "100", "chain": "base"}),
            ("check_onchain_risk", {"asset_id": "DEGEN", "chain": "base"}),
            None,
        ]

        def __init__(self):
            self.calls = 0

        def create_message(self, **kwargs):
            item = self.sequence[self.calls]
            self.calls += 1
            if item is None:
                return SimpleNamespace(
                    content=[SimpleNamespace(type="text", text="I checked the DEGEN balance and quote first, and deferred extra scans.")]
                )
            tool_name, tool_input = item
            return SimpleNamespace(
                content=[SimpleNamespace(type="tool_use", name=tool_name, input=tool_input, id=f"tool-{self.calls}")]
            )

    fake_client = FakeClient()
    executed = []

    monkeypatch.setattr(agent_module, "create_client", lambda provider: fake_client)
    monkeypatch.setattr(
        agent_module,
        "get_tool_definitions",
        lambda: [{"name": "get_tracked_token_balance"}, {"name": "trust_get_swap_quote"}, {"name": "check_onchain_risk"}],
    )
    monkeypatch.setattr(agent_module, "latest_summary", lambda sid: None)
    monkeypatch.setattr(agent_module, "save_session_for_provider", lambda *args, **kwargs: None)
    monkeypatch.setattr(agent_module, "execute_tool", lambda name, raw_input: executed.append((name, raw_input)) or f"result {name}")

    agent = Agent(provider=ModelProvider.ANTHROPIC, sid="test", history=[])

    response = agent.chat("sell remaining DEGEN")

    assert "deferred extra scans" in response
    assert executed == [
        ("get_tracked_token_balance", {"symbol": "DEGEN", "chain": "base"}),
        ("trust_get_swap_quote", {"from_token": "DEGEN", "to_token": "ETH", "amount": "100", "chain": "base"}),
    ]


def test_degen_watch_request_blocks_market_report_fanout(monkeypatch):
    class FakeClient:
        model = "fake"

        def __init__(self):
            self.calls = 0

        def create_message(self, **kwargs):
            self.calls += 1
            if self.calls == 1:
                return SimpleNamespace(
                    content=[SimpleNamespace(type="tool_use", name="market_report", input={"symbols": ["DEGEN"]}, id="tool-1")]
                )
            return SimpleNamespace(
                content=[
                    SimpleNamespace(
                        type="text",
                        text="I’m watching DEGEN with price-first staging and deferred the broader scans.",
                    )
                ]
            )

    fake_client = FakeClient()
    executed = []

    monkeypatch.setattr(agent_module, "create_client", lambda provider: fake_client)
    monkeypatch.setattr(
        agent_module,
        "get_tool_definitions",
        lambda: [{"name": "market_report"}, {"name": "trust_get_token_price"}, {"name": "trade_decision_engine"}],
    )
    monkeypatch.setattr(agent_module, "latest_summary", lambda sid: None)
    monkeypatch.setattr(agent_module, "save_session_for_provider", lambda *args, **kwargs: None)
    monkeypatch.setattr(agent_module, "execute_tool", lambda name, raw_input: executed.append((name, raw_input)) or "ok")

    agent = Agent(provider=ModelProvider.ANTHROPIC, sid="test", history=[])

    response = agent.chat("continue to look for opportunity or watch DEGEN price to come down then buy back in")

    assert response == "I’m watching DEGEN with price-first staging and deferred the broader scans."
    assert executed == []


def test_telegram_agent_prompt_prefers_composite_analysis(monkeypatch):
    class FakeClient:
        model = "fake"

    monkeypatch.setattr(agent_module, "create_client", lambda provider: FakeClient())
    monkeypatch.setattr(agent_module, "get_tool_definitions", lambda: [])
    monkeypatch.setattr(agent_module, "latest_summary", lambda sid: None)
    monkeypatch.setattr(agent_module, "save_session_for_provider", lambda *args, **kwargs: None)

    agent = Agent(provider=ModelProvider.ANTHROPIC, sid="test", user_id=123, history=[])

    assert "Telegram requests have a strict tool-call budget" in agent.system_prompt
    assert "trade_decision_engine" in agent.system_prompt
    assert "market_report" in agent.system_prompt


def test_telegram_repeat_guard_blocks_same_search_tool_too_many_times(monkeypatch):
    monkeypatch.delenv("TELEGRAM_MAX_REPEAT_PER_TOOL", raising=False)

    message = _telegram_tool_repeat_guard(
        "web_search",
        {"web_search": 2},
        telegram_search_like_calls=2,
    )

    assert message is not None
    assert "repeating `web_search` too many times" in message


def test_telegram_repeat_guard_blocks_excessive_search_fanout(monkeypatch):
    monkeypatch.delenv("TELEGRAM_MAX_SEARCH_LIKE_CALLS", raising=False)

    message = _telegram_tool_repeat_guard(
        "trust_search_token",
        {"trust_search_token": 1},
        telegram_search_like_calls=4,
    )

    assert message is not None
    assert "too many search-style tool calls" in message


def test_telegram_repeat_guard_blocks_all_search_after_guard_activation():
    message = _telegram_tool_repeat_guard(
        "web_search",
        {"web_search": 0},
        telegram_search_like_calls=0,
        guard_active=True,
    )

    assert message is not None
    assert "already active" in message


def test_telegram_tool_guard_result_tells_model_to_answer_without_more_search():
    result = _telegram_tool_guard_result("trust_search_token", "Refine the symbol, chain, or goal.")

    assert "intercepted `trust_search_token`" in result
    assert "Do not call additional search-style tools" in result
