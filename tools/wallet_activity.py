"""
Wallet activity tracker for background alerts.

This module keeps the wallet-watch logic isolated so the alert processor can
poll a deployer or whale address without depending on the rest of the trading
stack.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import requests

logger = logging.getLogger(__name__)


@dataclass
class WalletActivitySnapshot:
    wallet_address: str
    chain: str
    latest_tx_hash: Optional[str]
    latest_block_number: Optional[int]
    latest_tx: Optional[Dict[str, Any]]
    recent_txs: List[Dict[str, Any]]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "wallet_address": self.wallet_address,
            "chain": self.chain,
            "latest_tx_hash": self.latest_tx_hash,
            "latest_block_number": self.latest_block_number,
            "latest_tx": self.latest_tx,
            "recent_txs": self.recent_txs,
            "checked_at": datetime.now(timezone.utc).isoformat(),
        }


class BaseScanWalletActivityTracker:
    """Minimal BaseScan-backed wallet activity tracker."""

    BASESCAN_URL = "https://api.basescan.org/api"

    def __init__(self, api_key: Optional[str] = None, session: Optional[requests.Session] = None):
        self.api_key = api_key or os.getenv("BASESCAN_API_KEY", "YourApiKeyToken")
        self.session = session or requests.Session()

    def get_recent_transactions(self, wallet_address: str, chain: str = "base", limit: int = 5) -> List[Dict[str, Any]]:
        """Fetch recent normal transactions for a wallet."""
        params = {
            "module": "account",
            "action": "txlist",
            "address": wallet_address,
            "page": 1,
            "offset": limit,
            "sort": "desc",
            "apikey": self.api_key,
        }
        response = self.session.get(self.BASESCAN_URL, params=params, timeout=15)
        response.raise_for_status()
        payload = response.json()

        if not isinstance(payload, dict):
            raise ValueError("Unexpected BaseScan response shape")

        result = payload.get("result", [])
        if isinstance(result, list):
            return result

        message = payload.get("message", "Unknown BaseScan error")
        raise ValueError(message)

    def get_latest_activity(self, wallet_address: str, chain: str = "base") -> WalletActivitySnapshot:
        """Return the latest known transaction activity for a wallet."""
        recent_txs = self.get_recent_transactions(wallet_address, chain=chain, limit=5)
        latest_tx = recent_txs[0] if recent_txs else None

        latest_hash = None
        latest_block = None
        if latest_tx:
            latest_hash = latest_tx.get("hash")
            block_raw = latest_tx.get("blockNumber")
            try:
                latest_block = int(block_raw) if block_raw is not None else None
            except (TypeError, ValueError):
                latest_block = None

        return WalletActivitySnapshot(
            wallet_address=wallet_address,
            chain=chain,
            latest_tx_hash=latest_hash,
            latest_block_number=latest_block,
            latest_tx=latest_tx,
            recent_txs=recent_txs,
        )


def get_latest_wallet_activity(wallet_address: str, chain: str = "base") -> Dict[str, Any]:
    """Helper used by alert creation and the background processor."""
    tracker = BaseScanWalletActivityTracker()
    return tracker.get_latest_activity(wallet_address, chain=chain).to_dict()


def check_wallet_activity(
    wallet_address: str,
    chain: str = "base",
    last_seen_tx_hash: Optional[str] = None,
) -> Dict[str, Any]:
    """Check whether a wallet has new activity since the stored cursor."""
    tracker = BaseScanWalletActivityTracker()
    snapshot = tracker.get_latest_activity(wallet_address, chain=chain)

    latest_hash = snapshot.latest_tx_hash
    has_new_activity = bool(latest_hash and latest_hash != last_seen_tx_hash)

    return {
        "wallet_address": wallet_address,
        "chain": chain,
        "last_seen_tx_hash": last_seen_tx_hash,
        "latest_tx_hash": latest_hash,
        "latest_block_number": snapshot.latest_block_number,
        "has_new_activity": has_new_activity,
        "latest_tx": snapshot.latest_tx,
        "recent_txs": snapshot.recent_txs,
    }
