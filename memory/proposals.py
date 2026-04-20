import json
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional
from datetime import datetime

PROPOSAL_PATH = Path.home() / ".agent" / "proposals.json"

class ProposalStore:
    """Manages pending trade proposals for human-in-the-loop execution."""

    def __init__(self, path: Path | None = None):
        self.path = path or PROPOSAL_PATH
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self._save({})

    def _load(self) -> Dict[str, Any]:
        try:
            return json.loads(self.path.read_text())
        except (json.JSONDecodeError, OSError):
            return {}

    def _save(self, data: Dict[str, Any]) -> None:
        self.path.write_text(json.dumps(data, indent=2))

    def add_proposal(self, proposal_data: Dict[str, Any]) -> str:
        """Add a new proposal and return its ID."""
        proposals = self._load()
        pid = str(uuid.uuid4())[:8]
        proposal_data["id"] = pid
        proposal_data["created_at"] = datetime.utcnow().isoformat()
        proposal_data["status"] = "pending"
        proposals[pid] = proposal_data
        self._save(proposals)
        return pid

    def get_proposal(self, pid: str) -> Optional[Dict[str, Any]]:
        return self._load().get(pid)

    def update_proposal(self, pid: str, status: str) -> bool:
        proposals = self._load()
        if pid in proposals:
            proposals[pid]["status"] = status
            proposals[pid]["updated_at"] = datetime.utcnow().isoformat()
            self._save(proposals)
            return True
        return False

    def list_pending(self) -> List[Dict[str, Any]]:
        return [p for p in self._load().values() if p["status"] == "pending"]
