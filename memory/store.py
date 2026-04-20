import json
import uuid
from pathlib import Path
from typing import Any

SESSION_DIR = Path.home() / ".agent" / "sessions"


def _ensure_session_dir() -> Path:
    dir_path = SESSION_DIR.expanduser().resolve()
    dir_path.mkdir(parents=True, exist_ok=True)
    return dir_path


def new_session() -> str:
    """Create a new session and return its ID."""
    sid = uuid.uuid4().hex[:12]
    _ensure_session_dir()
    return sid


def save_session(sid: str, messages: list[dict[str, Any]]) -> None:
    """Persist the full message list for a session."""
    save_session_for_provider(sid, messages, provider=None)


def save_session_for_provider(
    sid: str,
    messages: list[dict[str, Any]],
    provider: str | None = None,
) -> None:
    """Persist a message list, optionally scoped to a provider."""
    path = _ensure_session_dir() / _session_filename(sid, provider)
    path.write_text(json.dumps({"session_id": sid, "provider": provider, "messages": messages}, indent=2))


def load_session(sid: str) -> list[dict[str, Any]]:
    """Load a session's message history. Returns empty list if not found."""
    path = _ensure_session_dir() / f"{sid}.json"
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text())
        return data.get("messages", [])
    except (json.JSONDecodeError, OSError):
        return []


def load_last_session() -> tuple[str | None, list[dict[str, Any]]]:
    """Find the most recently modified session file. Returns (sid, messages)."""
    return load_last_session_for_provider(provider=None)


def load_last_session_for_provider(provider: str | None = None) -> tuple[str | None, list[dict[str, Any]]]:
    """Find the most recently modified session file for a provider."""
    dir_path = _ensure_session_dir()
    if not dir_path.exists():
        return None, []
    pattern = f"{provider}-*.json" if provider else "*.json"
    files = sorted(dir_path.glob(pattern), key=lambda p: p.stat().st_mtime)
    if not files:
        return None, []
    latest = files[-1]
    try:
        data = json.loads(latest.read_text())
        return data.get("session_id", latest.stem), data.get("messages", [])
    except (json.JSONDecodeError, OSError):
        return None, []


def _session_filename(sid: str, provider: str | None = None) -> str:
    if provider:
        safe_provider = provider.replace("/", "-").replace(":", "-")
        if sid.startswith(f"{safe_provider}-"):
            return f"{sid}.json"
        return f"{safe_provider}-{sid}.json"
    return f"{sid}.json"
