import json
import os
from pathlib import Path
from typing import Any, Dict, List

DEFAULT_WISDOM_PATH = Path.home() / ".agent" / "wisdom.json"

class WisdomStore:
    """Manages the Agent Wisdom Ledger (long-term memory)."""

    def __init__(self, path: Path | None = None):
        self.path = path or DEFAULT_WISDOM_PATH
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self._save({"lessons": [], "commandments": []})

    def _load(self) -> Dict[str, List[Any]]:
        try:
            return json.loads(self.path.read_text())
        except (json.JSONDecodeError, OSError):
            return {"lessons": [], "commandments": []}

    def _save(self, data: Dict[str, List[Any]]) -> None:
        self.path.write_text(json.dumps(data, indent=2))

    def add_lesson(self, trade_symbol: str, pnl: float, lesson_text: str) -> None:
        """Add a specific observation from a trade."""
        data = self._load()
        data["lessons"].append({
            "symbol": trade_symbol,
            "pnl": pnl,
            "lesson": lesson_text
        })
        self._save(data)

    def add_commandment(self, rule_text: str) -> None:
        """Add a generalized rule for future trading."""
        data = self._load()
        if rule_text not in data["commandments"]:
            data["commandments"].append(rule_text)
            self._save(data)

    def get_commandments(self) -> List[str]:
        """Retrieve all current commandments."""
        return self._load().get("commandments", [])
    
    def get_lessons(self) -> List[Dict[str, Any]]:
        return self._load().get("lessons", [])
