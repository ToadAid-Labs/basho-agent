import json
import os
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime

class WalletStore:
    """Persistent storage for discovered Alpha Wallets."""
    
    def __init__(self, filename: str = "alpha_wallets.json"):
        self.file_path = Path.home() / ".agent" / "memory" / filename
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.file_path.exists():
            self.save_wallets([])

    def load_wallets(self) -> List[Dict[str, Any]]:
        try:
            return json.loads(self.file_path.read_text())
        except (json.JSONDecodeError, OSError):
            return []

    def save_wallets(self, wallets: List[Dict[str, Any]]):
        self.file_path.write_text(json.dumps(wallets, indent=2))

    def add_wallet(self, address: str, chain: str, tags: List[str] = None, notes: str = ""):
        wallets = self.load_wallets()
        address = address.lower()
        
        # Check if already exists
        for w in wallets:
            if w["address"].lower() == address and w["chain"] == chain:
                # Update existing
                if tags:
                    w["tags"] = list(set(w.get("tags", []) + tags))
                if notes:
                    w["notes"] = notes
                w["last_seen"] = datetime.now().isoformat()
                self.save_wallets(wallets)
                return

        # Add new
        wallets.append({
            "address": address,
            "chain": chain,
            "tags": tags or ["alpha"],
            "notes": notes,
            "added_at": datetime.now().isoformat(),
            "last_seen": datetime.now().isoformat(),
            "confidence": 0.5 # Initial confidence
        })
        self.save_wallets(wallets)

    def get_wallets_by_chain(self, chain: str) -> List[str]:
        wallets = self.load_wallets()
        return [w["address"] for w in wallets if w["chain"] == chain]

    def update_confidence(self, address: str, chain: str, adjustment: float):
        wallets = self.load_wallets()
        for w in wallets:
            if w["address"].lower() == address.lower() and w["chain"] == chain:
                w["confidence"] = max(0.0, min(1.0, w.get("confidence", 0.5) + adjustment))
                break
        self.save_wallets(wallets)
