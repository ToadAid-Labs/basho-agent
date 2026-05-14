import json

from tools import trust_wallet


def _mock_run_twak_factory(summary_rows, direct_output, addresses_output=None):
    addresses_text = addresses_output or (
        "╭ wallet ╮\n"
        "│ Chains  base ethereum │\n"
        "│ Address 0xAC710b6959995b206261A7148801716ce32C65cF │\n"
        "╰────────╯"
    )

    def _mock_run_twak(args, timeout=None):
        if args == ["wallet", "portfolio", "--chains", "base", "--json"]:
            return json.dumps(summary_rows)
        if args == ["wallet", "addresses"]:
            return addresses_text
        if args == [
            "balance",
            "--chain",
            "base",
            "--address",
            "0xAC710b6959995b206261A7148801716ce32C65cF",
            "--token",
            "0x4ed4e862860beD51a9570b96d89aF5E1B0Efefed",
            "--json",
        ]:
            return direct_output
        raise AssertionError(f"Unexpected twak args: {args}")

    return _mock_run_twak


def test_wallet_portfolio_merges_direct_tracked_token_balance(monkeypatch):
    summary_rows = [
        {
            "chain": "base",
            "type": "native",
            "symbol": "ETH",
            "balance": "0.1",
            "usdValue": 250.0,
        },
        {
            "chain": "base",
            "type": "token",
            "symbol": "USDC",
            "balance": "100",
            "usdValue": 100.0,
        },
    ]
    monkeypatch.setattr(
        trust_wallet,
        "run_twak",
        _mock_run_twak_factory(
            summary_rows=summary_rows,
            direct_output=json.dumps({"balance": "52577.277414"}),
        ),
    )

    result = trust_wallet.get_wallet_portfolio(["base"])

    assert "USDC" in result
    assert "DEGEN" in result
    assert "52577.277414" in result
    assert "No non-zero balances found" not in result


def test_wallet_portfolio_reports_unknown_when_direct_lookup_fails(monkeypatch):
    monkeypatch.setattr(
        trust_wallet,
        "run_twak",
        _mock_run_twak_factory(
            summary_rows=[],
            direct_output="Error: rpc timeout",
        ),
    )

    result = trust_wallet.get_wallet_portfolio(["base"])

    assert "DEGEN" in result
    assert "unknown" in result.lower()
    assert "0" not in result.split("DEGEN", 1)[1].splitlines()[0]


def test_wallet_portfolio_reports_zero_when_direct_lookup_confirms_zero(monkeypatch):
    monkeypatch.setattr(
        trust_wallet,
        "run_twak",
        _mock_run_twak_factory(
            summary_rows=[],
            direct_output=json.dumps({"balance": "0"}),
        ),
    )

    result = trust_wallet.get_wallet_portfolio(["base"])

    assert "DEGEN" in result
    assert "  0  " in result or result.rstrip().endswith("0  Unknown")


def test_wallet_portfolio_does_not_mark_absent_before_direct_check(monkeypatch):
    monkeypatch.setattr(
        trust_wallet,
        "run_twak",
        _mock_run_twak_factory(
            summary_rows=[],
            direct_output="Error: upstream unavailable",
        ),
    )

    result = trust_wallet.get_wallet_portfolio(["base"])

    assert "No non-zero balances found across the configured portfolio chains." not in result
    assert "DEGEN" in result
