import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_RAW_CONTEXT_MESSAGES = 10
DEFAULT_SUMMARY_THRESHOLD_MESSAGES = 20


def default_db_path() -> Path:
    configured = os.getenv("AGENT_CONTINUITY_DB_PATH")
    if configured:
        return Path(configured).expanduser()
    return Path.home() / ".agent" / "continuity.sqlite3"


class ContinuityStore:
    """SQLite-backed conversation spine for restart-safe continuity."""

    def __init__(self, path: Path | str | None = None):
        self.path = Path(path).expanduser() if path is not None else default_db_path()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.init_db()

    def init_db(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                PRAGMA journal_mode=WAL;

                CREATE TABLE IF NOT EXISTS sessions (
                    id TEXT PRIMARY KEY,
                    user_id TEXT,
                    thread_id TEXT,
                    started_at TEXT NOT NULL,
                    last_active_at TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'active'
                );

                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    metadata_json TEXT,
                    FOREIGN KEY(session_id) REFERENCES sessions(id)
                );

                CREATE TABLE IF NOT EXISTS summaries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    last_message_id INTEGER NOT NULL,
                    summary_content TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(session_id) REFERENCES sessions(id),
                    FOREIGN KEY(last_message_id) REFERENCES messages(id)
                );

                CREATE TABLE IF NOT EXISTS trading_decisions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT,
                    symbol TEXT,
                    contract_address TEXT,
                    chain TEXT,
                    action TEXT,
                    confidence REAL,
                    regime TEXT,
                    forge_signals_json TEXT,
                    technical_snapshot_json TEXT,
                    reasoning TEXT,
                    linked_prediction_id TEXT,
                    created_at TEXT NOT NULL,
                    outcome_status TEXT,
                    FOREIGN KEY(session_id) REFERENCES sessions(id)
                );

                CREATE INDEX IF NOT EXISTS idx_sessions_thread_last_active
                    ON sessions(thread_id, last_active_at);
                CREATE INDEX IF NOT EXISTS idx_messages_session_id
                    ON messages(session_id, id);
                CREATE INDEX IF NOT EXISTS idx_summaries_session_id
                    ON summaries(session_id, id);
                CREATE INDEX IF NOT EXISTS idx_trading_decisions_session_id
                    ON trading_decisions(session_id, id);
                CREATE INDEX IF NOT EXISTS idx_trading_decisions_linked_prediction
                    ON trading_decisions(linked_prediction_id);
                """
            )

    def upsert_session(
        self,
        session_id: str,
        *,
        user_id: str | int | None = None,
        thread_id: str | None = None,
        status: str = "active",
    ) -> None:
        now = _utc_now()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO sessions (id, user_id, thread_id, started_at, last_active_at, status)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    user_id = COALESCE(excluded.user_id, sessions.user_id),
                    thread_id = COALESCE(excluded.thread_id, sessions.thread_id),
                    last_active_at = excluded.last_active_at,
                    status = excluded.status
                """,
                (session_id, _string_or_none(user_id), thread_id, now, now, status),
            )

    def save_messages(
        self,
        session_id: str,
        messages: list[dict[str, Any]],
        *,
        user_id: str | int | None = None,
        thread_id: str | None = None,
    ) -> None:
        self.upsert_session(session_id, user_id=user_id, thread_id=thread_id)
        now = _utc_now()
        with self._connect() as conn:
            existing_count = conn.execute(
                "SELECT COUNT(*) FROM messages WHERE session_id = ?",
                (session_id,),
            ).fetchone()[0]
            new_messages = messages[existing_count:]
            if not new_messages:
                conn.execute(
                    "UPDATE sessions SET last_active_at = ? WHERE id = ?",
                    (now, session_id),
                )
                return

            rows = []
            for ordinal, message in enumerate(new_messages, start=existing_count):
                role = str(message.get("role", "user"))
                content, metadata = _serialize_content(message.get("content", ""))
                metadata["ordinal"] = ordinal
                rows.append((session_id, role, content, now, json.dumps(metadata, sort_keys=True)))

            conn.executemany(
                """
                INSERT INTO messages (session_id, role, content, created_at, metadata_json)
                VALUES (?, ?, ?, ?, ?)
                """,
                rows,
            )
            conn.execute(
                "UPDATE sessions SET last_active_at = ? WHERE id = ?",
                (now, session_id),
            )

    def load_messages(self, session_id: str) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT role, content, metadata_json
                FROM messages
                WHERE session_id = ?
                ORDER BY id ASC
                """,
                (session_id,),
            ).fetchall()
        return [_row_to_message(row) for row in rows]

    def load_last_session(
        self,
        *,
        thread_id: str | None = None,
    ) -> tuple[str | None, list[dict[str, Any]]]:
        sql = "SELECT id FROM sessions WHERE status = 'active'"
        params: list[Any] = []
        if thread_id is not None:
            sql += " AND thread_id = ?"
            params.append(thread_id)
        sql += " ORDER BY last_active_at DESC LIMIT 1"

        with self._connect() as conn:
            row = conn.execute(sql, params).fetchone()
        if row is None:
            return None, []
        session_id = row[0]
        return session_id, self.load_messages(session_id)

    def latest_summary(self, session_id: str) -> str | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT summary_content
                FROM summaries
                WHERE session_id = ?
                ORDER BY id DESC
                LIMIT 1
                """,
                (session_id,),
            ).fetchone()
        return row[0] if row else None

    def maybe_summarize(
        self,
        session_id: str,
        *,
        raw_context_messages: int = DEFAULT_RAW_CONTEXT_MESSAGES,
        threshold_messages: int = DEFAULT_SUMMARY_THRESHOLD_MESSAGES,
    ) -> str | None:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT id, role, content, metadata_json
                FROM messages
                WHERE session_id = ?
                ORDER BY id ASC
                """,
                (session_id,),
            ).fetchall()
            if len(rows) < threshold_messages:
                return self.latest_summary(session_id)

            cutoff = max(0, len(rows) - max(raw_context_messages, 1))
            if cutoff <= 0:
                return self.latest_summary(session_id)

            last_message_id = rows[cutoff - 1][0]
            latest = conn.execute(
                """
                SELECT last_message_id, summary_content
                FROM summaries
                WHERE session_id = ?
                ORDER BY id DESC
                LIMIT 1
                """,
                (session_id,),
            ).fetchone()
            if latest and int(latest[0]) >= int(last_message_id):
                return latest[1]

            summary = _compact_summary(rows[:cutoff])
            conn.execute(
                """
                INSERT INTO summaries (session_id, last_message_id, summary_content, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (session_id, last_message_id, summary, _utc_now()),
            )
            return summary

    def reset_thread(self, thread_id: str) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE sessions
                SET status = 'reset', last_active_at = ?
                WHERE thread_id = ? AND status = 'active'
                """,
                (_utc_now(), thread_id),
            )

    def record_trading_decision(
        self,
        *,
        session_id: str | None = None,
        symbol: str | None = None,
        contract_address: str | None = None,
        chain: str | None = None,
        action: str | None = None,
        confidence: float | None = None,
        regime: str | None = None,
        forge_signals: dict[str, Any] | list[Any] | None = None,
        technical_snapshot: dict[str, Any] | list[Any] | None = None,
        reasoning: str | None = None,
        linked_prediction_id: str | None = None,
        outcome_status: str | None = None,
    ) -> int:
        """Store a future-facing decision record without touching Forge JSON artifacts."""
        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO trading_decisions (
                    session_id,
                    symbol,
                    contract_address,
                    chain,
                    action,
                    confidence,
                    regime,
                    forge_signals_json,
                    technical_snapshot_json,
                    reasoning,
                    linked_prediction_id,
                    created_at,
                    outcome_status
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session_id,
                    symbol,
                    contract_address,
                    chain,
                    action,
                    confidence,
                    regime,
                    _json_or_none(forge_signals),
                    _json_or_none(technical_snapshot),
                    reasoning,
                    linked_prediction_id,
                    _utc_now(),
                    outcome_status,
                ),
            )
            return int(cursor.lastrowid)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.execute("PRAGMA foreign_keys=ON")
        return conn


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _string_or_none(value: str | int | None) -> str | None:
    if value is None:
        return None
    return str(value)


def _serialize_content(content: Any) -> tuple[str, dict[str, Any]]:
    if isinstance(content, str):
        return content, {"content_type": "text"}
    return json.dumps(content, ensure_ascii=False), {"content_type": "json"}


def _json_or_none(value: dict[str, Any] | list[Any] | None) -> str | None:
    if value is None:
        return None
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _row_to_message(row: sqlite3.Row | tuple[Any, ...]) -> dict[str, Any]:
    role, content, metadata_json = row
    metadata = _parse_metadata(metadata_json)
    if metadata.get("content_type") == "json":
        try:
            parsed_content = json.loads(content)
        except json.JSONDecodeError:
            parsed_content = content
    else:
        parsed_content = content
    return {"role": role, "content": parsed_content}


def _parse_metadata(metadata_json: str | None) -> dict[str, Any]:
    if not metadata_json:
        return {}
    try:
        metadata = json.loads(metadata_json)
    except json.JSONDecodeError:
        return {}
    return metadata if isinstance(metadata, dict) else {}


def _compact_summary(rows: list[tuple[Any, ...]]) -> str:
    snippets: list[str] = []
    for row in rows[-12:]:
        _, role, content, metadata_json = row
        metadata = _parse_metadata(metadata_json)
        if metadata.get("content_type") == "json":
            try:
                content = _tool_aware_text(json.loads(content))
            except json.JSONDecodeError:
                pass
        text = _single_line(str(content))
        if not text:
            continue
        snippets.append(f"{role}: {_truncate(text, 280)}")

    if not snippets:
        return "Earlier conversation exists in SQLite, but it did not contain compact text content."
    return (
        "Compact continuity summary of earlier turns. Preserve user goals, open tasks, "
        "trading preferences, and unresolved decisions:\n"
        + "\n".join(f"- {snippet}" for snippet in snippets)
    )


def _tool_aware_text(content: Any) -> str:
    if not isinstance(content, list):
        return str(content)

    parts: list[str] = []
    for block in content:
        if not isinstance(block, dict):
            continue
        block_type = block.get("type")
        if block_type == "text":
            parts.append(str(block.get("text", "")))
        elif block_type == "tool_use":
            parts.append(f"tool_use:{block.get('name', 'unknown')}")
        elif block_type == "tool_result":
            parts.append(f"tool_result:{block.get('name', 'unknown')}={block.get('content', '')}")
    return " | ".join(part for part in parts if part)


def _single_line(text: str) -> str:
    return " ".join(text.split())


def _truncate(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 14].rstrip() + " ...[truncated]"
