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


def test_get_wallet_balance_without_chain_uses_tracked_portfolio_view(monkeypatch):
    monkeypatch.setattr(trust_wallet, "get_wallet_portfolio", lambda chains=None: "tracked portfolio view")

    result = trust_wallet.get_wallet_balance()

    assert result == "tracked portfolio view"


def test_get_tracked_token_balance_returns_direct_lookup(monkeypatch):
    monkeypatch.setattr(
        trust_wallet,
        "_get_direct_tracked_token_row",
        lambda symbol, chain=None: {"status": "ok", "symbol": symbol, "chain": chain or "base", "balance": "12.5"},
    )

    result = trust_wallet.get_tracked_token_balance("DEGEN", "base")

    assert '"symbol": "DEGEN"' in result
    assert '"balance": "12.5"' in result


def test_transfer_uses_saved_local_credential_flow_without_password_prompt(monkeypatch):
    calls = []

    def _mock_run_twak(args, timeout=None):
        calls.append(args)
        if args == ["transfer", "--chain", "base", "--to", "0xabc", "--amount", "1.25"]:
            return '{"txHash":"0x1111111111111111111111111111111111111111111111111111111111111111"}'
        raise AssertionError(f"Unexpected twak args: {args}")

    monkeypatch.setattr(trust_wallet, "run_twak", _mock_run_twak)
    monkeypatch.setenv("TWAK_WALLET_PASSWORD", "stored-locally")

    result = trust_wallet.transfer_tokens("base", "0xabc", "1.25")

    assert "--password" not in calls[0]
    assert "Verified tx hash: 0x1111111111111111111111111111111111111111111111111111111111111111" == result
    assert "please provide your wallet password" not in result.lower()


def test_locked_signer_redirects_to_secure_local_unlock(monkeypatch):
    def _mock_run_twak(args, timeout=None):
        if args == ["wallet", "status"]:
            return "Wallet signer is locked."
        raise AssertionError(f"Unexpected twak args: {args}")

    monkeypatch.setattr(trust_wallet, "run_twak", _mock_run_twak)
    monkeypatch.delenv("TWAK_WALLET_PASSWORD", raising=False)
    monkeypatch.delenv("TWAK_WALLET_SESSION", raising=False)

    result = trust_wallet.transfer_tokens("base", "0xabc", "1.25")

    assert result == trust_wallet.SECURE_TWAK_UNLOCK_MESSAGE


def test_execution_response_rewrites_wallet_password_prompt(monkeypatch):
    def _mock_run_twak(args, timeout=None):
        if args == ["swap", "--chain", "base", "10", "ETH", "DEGEN", "--execute"]:
            return "Error: please provide your wallet password to continue"
        raise AssertionError(f"Unexpected twak args: {args}")

    monkeypatch.setattr(trust_wallet, "run_twak", _mock_run_twak)
    monkeypatch.setenv("TWAK_WALLET_PASSWORD", "stored-locally")

    result = trust_wallet.swap_tokens("base", "10", "ETH", "DEGEN", execute=True)

    assert result.endswith(trust_wallet.SECURE_TWAK_UNLOCK_MESSAGE)
    assert "please provide your wallet password" not in result.lower()


def test_successful_swap_execution_reports_verified_tx_hash(monkeypatch):
    def _mock_run_twak(args, timeout=None):
        if args == ["swap", "--chain", "base", "10", "ETH", "DEGEN", "--execute"]:
            return '{"result":{"transactionHash":"0x2222222222222222222222222222222222222222222222222222222222222222"}}'
        raise AssertionError(f"Unexpected twak args: {args}")

    monkeypatch.setattr(trust_wallet, "run_twak", _mock_run_twak)
    monkeypatch.setenv("TWAK_WALLET_PASSWORD", "stored-locally")

    result = trust_wallet.swap_tokens("base", "10", "ETH", "DEGEN", execute=True)

    assert "Verified tx hash: 0x2222222222222222222222222222222222222222222222222222222222222222" in result
