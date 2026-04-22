import json
import logging
import uuid
from pathlib import Path
from typing import Any

from memory.continuity import ContinuityStore

logger = logging.getLogger(__name__)
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
    *,
    user_id: str | int | None = None,
    thread_id: str | None = None,
) -> None:
    """Persist a message list, optionally scoped to a provider."""
    continuity_thread_id = thread_id or provider
    try:
        store = ContinuityStore()
        store.save_messages(
            sid,
            messages,
            user_id=user_id,
            thread_id=continuity_thread_id,
        )
        store.maybe_summarize(sid)
    except Exception as e:  # noqa: BLE001
        logger.warning("SQLite continuity save failed for session %s: %s", sid, e)

    path = _ensure_session_dir() / _session_filename(sid, provider)
    path.write_text(json.dumps({"session_id": sid, "provider": provider, "messages": messages}, indent=2))


def load_session(sid: str) -> list[dict[str, Any]]:
    """Load a session's message history. Returns empty list if not found."""
    try:
        continuity_messages = ContinuityStore().load_messages(sid)
        if continuity_messages:
            return continuity_messages
    except Exception as e:  # noqa: BLE001
        logger.warning("SQLite continuity load failed for session %s: %s", sid, e)

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
    try:
        sid, messages = ContinuityStore().load_last_session(thread_id=provider)
        if sid:
            return sid, messages
    except Exception as e:  # noqa: BLE001
        logger.warning("SQLite continuity latest-session load failed for provider %s: %s", provider, e)

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


def load_last_session_for_thread(thread_id: str) -> tuple[str | None, list[dict[str, Any]]]:
    """Find the latest active SQLite session for an application thread."""
    try:
        return ContinuityStore().load_last_session(thread_id=thread_id)
    except Exception as e:  # noqa: BLE001
        logger.warning("SQLite continuity latest-session load failed for thread %s: %s", thread_id, e)
        return None, []


def latest_summary(sid: str) -> str | None:
    """Return the latest compact summary for a session, if one exists."""
    try:
        return ContinuityStore().latest_summary(sid)
    except Exception as e:  # noqa: BLE001
        logger.warning("SQLite continuity summary load failed for session %s: %s", sid, e)
        return None


def reset_sessions_for_thread(thread_id: str) -> None:
    """Mark active sessions for a thread as reset without deleting raw history."""
    try:
        ContinuityStore().reset_thread(thread_id)
    except Exception as e:  # noqa: BLE001
        logger.warning("SQLite continuity reset failed for thread %s: %s", thread_id, e)
