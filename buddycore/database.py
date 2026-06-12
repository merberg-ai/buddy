from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class BuddyDatabase:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def init_schema(self) -> None:
        with self.connect() as conn:
            conn.executescript(
                """
                PRAGMA journal_mode=WAL;

                CREATE TABLE IF NOT EXISTS plugins (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    version TEXT NOT NULL,
                    type TEXT,
                    description TEXT,
                    author TEXT,
                    path TEXT NOT NULL,
                    enabled INTEGER DEFAULT 0,
                    status TEXT DEFAULT 'installed',
                    source_type TEXT,
                    source_url TEXT,
                    source_branch TEXT,
                    source_commit TEXT,
                    installed_at TEXT NOT NULL,
                    updated_at TEXT,
                    last_started_at TEXT,
                    last_error TEXT
                );

                CREATE TABLE IF NOT EXISTS plugin_permissions (
                    plugin_id TEXT NOT NULL,
                    permission TEXT NOT NULL,
                    granted INTEGER DEFAULT 0,
                    required INTEGER DEFAULT 1,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (plugin_id, permission)
                );

                CREATE TABLE IF NOT EXISTS plugin_settings (
                    plugin_id TEXT NOT NULL,
                    key TEXT NOT NULL,
                    value_json TEXT,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (plugin_id, key)
                );

                CREATE TABLE IF NOT EXISTS plugin_errors (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    plugin_id TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    phase TEXT NOT NULL,
                    error_type TEXT,
                    error_message TEXT,
                    traceback TEXT,
                    event_type TEXT,
                    payload_json TEXT,
                    handled INTEGER DEFAULT 1
                );

                CREATE TABLE IF NOT EXISTS plugin_health (
                    plugin_id TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    error_count INTEGER DEFAULT 0,
                    last_error TEXT,
                    last_error_at TEXT,
                    last_started_at TEXT,
                    last_heartbeat_at TEXT,
                    auto_disabled INTEGER DEFAULT 0
                );

                CREATE TABLE IF NOT EXISTS event_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    level TEXT NOT NULL,
                    source TEXT NOT NULL,
                    plugin_id TEXT,
                    event_type TEXT,
                    message TEXT NOT NULL,
                    payload_json TEXT
                );

                CREATE TABLE IF NOT EXISTS conversations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    started_at TEXT NOT NULL,
                    ended_at TEXT,
                    title TEXT,
                    summary TEXT,
                    active INTEGER DEFAULT 1
                );

                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    conversation_id INTEGER,
                    timestamp TEXT NOT NULL,
                    role TEXT NOT NULL,
                    text TEXT NOT NULL,
                    audio_path TEXT,
                    image_path TEXT,
                    emotion TEXT,
                    FOREIGN KEY(conversation_id) REFERENCES conversations(id)
                );

                CREATE TABLE IF NOT EXISTS memories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    memory_type TEXT NOT NULL,
                    title TEXT,
                    content TEXT NOT NULL,
                    importance INTEGER DEFAULT 5,
                    confidence REAL DEFAULT 1.0,
                    source TEXT,
                    enabled INTEGER DEFAULT 1
                );
                """
            )

    def log_event(self, level: str, source: str, message: str, event_type: str | None = None, payload: Any = None, plugin_id: str | None = None) -> None:
        payload_json = json.dumps(payload, default=str) if payload is not None else None
        with self.connect() as conn:
            conn.execute(
                "INSERT INTO event_log (timestamp, level, source, plugin_id, event_type, message, payload_json) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (now_iso(), level, source, plugin_id, event_type, message, payload_json),
            )

    def recent_events(self, limit: int = 100, plugin_id: str | None = None) -> list[dict[str, Any]]:
        with self.connect() as conn:
            if plugin_id:
                rows = conn.execute(
                    """
                    SELECT * FROM event_log
                    WHERE plugin_id=? OR source=?
                    ORDER BY id DESC LIMIT ?
                    """,
                    (plugin_id, plugin_id, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM event_log ORDER BY id DESC LIMIT ?", (limit,)
                ).fetchall()
        return [dict(row) for row in reversed(rows)]

    def upsert_plugin(self, manifest: dict[str, Any], path: str, default_enabled: bool) -> None:
        now = now_iso()
        plugin_id = manifest["id"]
        with self.connect() as conn:
            existing = conn.execute("SELECT id FROM plugins WHERE id = ?", (plugin_id,)).fetchone()
            if existing:
                conn.execute(
                    """
                    UPDATE plugins
                    SET name=?, version=?, type=?, description=?, author=?, path=?, updated_at=?
                    WHERE id=?
                    """,
                    (
                        manifest.get("name", plugin_id),
                        str(manifest.get("version", "0.0.0")),
                        manifest.get("type", "utility"),
                        manifest.get("description", ""),
                        manifest.get("author", ""),
                        path,
                        now,
                        plugin_id,
                    ),
                )
            else:
                conn.execute(
                    """
                    INSERT INTO plugins (id, name, version, type, description, author, path, enabled, status, installed_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        plugin_id,
                        manifest.get("name", plugin_id),
                        str(manifest.get("version", "0.0.0")),
                        manifest.get("type", "utility"),
                        manifest.get("description", ""),
                        manifest.get("author", ""),
                        path,
                        1 if default_enabled else 0,
                        "installed",
                        now,
                    ),
                )
            for perm in manifest.get("permissions", []) or []:
                if isinstance(perm, dict):
                    permission = str(perm.get("name", ""))
                    required = 1 if bool(perm.get("required", True)) else 0
                else:
                    permission = str(perm)
                    required = 1
                if not permission:
                    continue
                conn.execute(
                    """
                    INSERT OR IGNORE INTO plugin_permissions (plugin_id, permission, granted, required, updated_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (plugin_id, permission, 1, required, now),
                )

    def get_plugin_permissions(self, plugin_id: str) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM plugin_permissions WHERE plugin_id=? ORDER BY permission COLLATE NOCASE",
                (plugin_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def set_plugin_permission(self, plugin_id: str, permission: str, granted: bool) -> bool:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT plugin_id, permission FROM plugin_permissions WHERE plugin_id=? AND permission=?",
                (plugin_id, permission),
            ).fetchone()
            if not row:
                return False
            conn.execute(
                "UPDATE plugin_permissions SET granted=?, updated_at=? WHERE plugin_id=? AND permission=?",
                (1 if granted else 0, now_iso(), plugin_id, permission),
            )
            return True

    def set_plugin_status(self, plugin_id: str, status: str, error: str | None = None) -> None:
        with self.connect() as conn:
            conn.execute(
                "UPDATE plugins SET status=?, last_error=?, updated_at=? WHERE id=?",
                (status, error, now_iso(), plugin_id),
            )
            conn.execute(
                """
                INSERT INTO plugin_health (plugin_id, status, last_error, last_error_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(plugin_id) DO UPDATE SET
                    status=excluded.status,
                    last_error=excluded.last_error,
                    last_error_at=excluded.last_error_at
                """,
                (plugin_id, status, error, now_iso() if error else None),
            )

    def set_plugin_enabled(self, plugin_id: str, enabled: bool) -> None:
        with self.connect() as conn:
            conn.execute("UPDATE plugins SET enabled=?, updated_at=? WHERE id=?", (1 if enabled else 0, now_iso(), plugin_id))

    def get_plugin_rows(self) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute("SELECT * FROM plugins ORDER BY name COLLATE NOCASE").fetchall()
        return [dict(row) for row in rows]

    def get_plugin_row(self, plugin_id: str) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM plugins WHERE id=?", (plugin_id,)).fetchone()
        return dict(row) if row else None

    def record_plugin_error(self, plugin_id: str, phase: str, error_type: str, error_message: str, traceback_text: str, event_type: str | None = None, payload: Any = None) -> None:
        payload_json = json.dumps(payload, default=str) if payload is not None else None
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO plugin_errors (plugin_id, timestamp, phase, error_type, error_message, traceback, event_type, payload_json, handled)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)
                """,
                (plugin_id, now_iso(), phase, error_type, error_message, traceback_text, event_type, payload_json),
            )
            conn.execute(
                """
                INSERT INTO plugin_health (plugin_id, status, error_count, last_error, last_error_at)
                VALUES (?, 'failed', 1, ?, ?)
                ON CONFLICT(plugin_id) DO UPDATE SET
                    status='failed',
                    error_count=plugin_health.error_count + 1,
                    last_error=excluded.last_error,
                    last_error_at=excluded.last_error_at
                """,
                (plugin_id, error_message, now_iso()),
            )
            conn.execute(
                "UPDATE plugins SET status='failed', last_error=?, updated_at=? WHERE id=?",
                (error_message, now_iso(), plugin_id),
            )

    def get_plugin_errors(self, plugin_id: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        with self.connect() as conn:
            if plugin_id:
                rows = conn.execute("SELECT * FROM plugin_errors WHERE plugin_id=? ORDER BY id DESC LIMIT ?", (plugin_id, limit)).fetchall()
            else:
                rows = conn.execute("SELECT * FROM plugin_errors ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        return [dict(row) for row in rows]
