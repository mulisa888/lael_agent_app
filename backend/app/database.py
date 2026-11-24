from __future__ import annotations

import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from app.config import DATA_DIR

DB_PATH = DATA_DIR / "lael.db"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Database:
    def __init__(self, path: Path = DB_PATH) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(str(self.path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA foreign_keys=ON;")
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init_schema(self) -> None:
        with self.connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS conversations (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS messages (
                    id TEXT PRIMARY KEY,
                    conversation_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    tool_events TEXT DEFAULT '[]',
                    provider TEXT DEFAULT '',
                    model TEXT DEFAULT '',
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS tasks (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    notes TEXT DEFAULT '',
                    status TEXT NOT NULL DEFAULT 'open',
                    priority TEXT NOT NULL DEFAULT 'medium',
                    due_date TEXT DEFAULT '',
                    tags TEXT DEFAULT '[]',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS notes (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    content TEXT NOT NULL,
                    tags TEXT DEFAULT '[]',
                    pinned INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS reminders (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    remind_at TEXT NOT NULL,
                    repeat TEXT DEFAULT 'none',
                    triggered INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS kb_files (
                    path TEXT PRIMARY KEY,
                    mtime REAL NOT NULL,
                    size INTEGER NOT NULL,
                    chunk_count INTEGER NOT NULL DEFAULT 0,
                    indexed_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS kb_chunks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    file_path TEXT NOT NULL,
                    chunk_index INTEGER NOT NULL,
                    content TEXT NOT NULL,
                    embedding TEXT DEFAULT '',
                    FOREIGN KEY (file_path) REFERENCES kb_files(path) ON DELETE CASCADE
                );

                CREATE VIRTUAL TABLE IF NOT EXISTS kb_chunks_fts USING fts5(
                    content,
                    file_path UNINDEXED,
                    content='kb_chunks',
                    content_rowid='id'
                );

                CREATE TRIGGER IF NOT EXISTS kb_chunks_ai AFTER INSERT ON kb_chunks BEGIN
                    INSERT INTO kb_chunks_fts(rowid, content, file_path)
                    VALUES (new.id, new.content, new.file_path);
                END;

                CREATE TRIGGER IF NOT EXISTS kb_chunks_ad AFTER DELETE ON kb_chunks BEGIN
                    INSERT INTO kb_chunks_fts(kb_chunks_fts, rowid, content, file_path)
                    VALUES ('delete', old.id, old.content, old.file_path);
                END;

                CREATE TABLE IF NOT EXISTS audit_log (
                    id TEXT PRIMARY KEY,
                    timestamp TEXT NOT NULL,
                    tool_name TEXT NOT NULL,
                    tier INTEGER NOT NULL,
                    summary TEXT NOT NULL,
                    details TEXT DEFAULT '{}',
                    status TEXT NOT NULL
                );
                """
            )

    # ---------------- Conversations & Messages ----------------
    def create_conversation(self, title: str = "New Chat") -> dict[str, Any]:
        cid = str(uuid.uuid4())
        now = utc_now()
        with self.connect() as conn:
            conn.execute(
                "INSERT INTO conversations (id, title, created_at, updated_at) VALUES (?, ?, ?, ?)",
                (cid, title, now, now),
            )
        return {"id": cid, "title": title, "created_at": now, "updated_at": now}

    def list_conversations(self) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT id, title, created_at, updated_at FROM conversations ORDER BY updated_at DESC"
            ).fetchall()
        return [dict(r) for r in rows]

    def get_conversation(self, cid: str) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT id, title, created_at, updated_at FROM conversations WHERE id = ?",
                (cid,),
            ).fetchone()
        return dict(row) if row else None

    def rename_conversation(self, cid: str, title: str) -> None:
        with self.connect() as conn:
            conn.execute(
                "UPDATE conversations SET title = ?, updated_at = ? WHERE id = ?",
                (title[:80], utc_now(), cid),
            )

    def delete_conversation(self, cid: str) -> None:
        with self.connect() as conn:
            conn.execute("DELETE FROM conversations WHERE id = ?", (cid,))

    def add_message(
        self,
        conversation_id: str,
        role: str,
        content: str,
        tool_events: list[dict[str, Any]] | None = None,
        provider: str = "",
        model: str = "",
    ) -> dict[str, Any]:
        mid = str(uuid.uuid4())
        now = utc_now()
        events_json = json.dumps(tool_events or [])
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO messages (id, conversation_id, role, content, tool_events, provider, model, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (mid, conversation_id, role, content, events_json, provider, model, now),
            )
            conn.execute(
                "UPDATE conversations SET updated_at = ? WHERE id = ?",
                (now, conversation_id),
            )
        return {
            "id": mid,
            "conversation_id": conversation_id,
            "role": role,
            "content": content,
            "tool_events": tool_events or [],
            "provider": provider,
            "model": model,
            "created_at": now,
        }

    def get_messages(self, conversation_id: str, limit: int = 100) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT id, conversation_id, role, content, tool_events, provider, model, created_at
                FROM messages
                WHERE conversation_id = ?
                ORDER BY created_at ASC
                LIMIT ?
                """,
                (conversation_id, limit),
            ).fetchall()
        out = []
        for r in rows:
            item = dict(r)
            try:
                item["tool_events"] = json.loads(item["tool_events"] or "[]")
            except Exception:
                item["tool_events"] = []
            out.append(item)
        return out

    # ---------------- Tasks ----------------
    def create_task(
        self,
        title: str,
        notes: str = "",
        priority: str = "medium",
        due_date: str = "",
        tags: list[str] | None = None,
    ) -> dict[str, Any]:
        tid = str(uuid.uuid4())[:8]
        now = utc_now()
        tags_list = tags or []
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO tasks (id, title, notes, status, priority, due_date, tags, created_at, updated_at)
                VALUES (?, ?, ?, 'open', ?, ?, ?, ?, ?)
                """,
                (tid, title, notes, priority, due_date, json.dumps(tags_list), now, now),
            )
        return {
            "id": tid,
            "title": title,
            "notes": notes,
            "status": "open",
            "priority": priority,
            "due_date": due_date,
            "tags": tags_list,
            "created_at": now,
            "updated_at": now,
        }

    def list_tasks(self, status: str | None = None) -> list[dict[str, Any]]:
        with self.connect() as conn:
            if status and status != "all":
                rows = conn.execute(
                    "SELECT * FROM tasks WHERE status = ? ORDER BY created_at DESC",
                    (status,),
                ).fetchall()
            else:
                rows = conn.execute("SELECT * FROM tasks ORDER BY status DESC, created_at DESC").fetchall()
        result = []
        for r in rows:
            d = dict(r)
            d["tags"] = json.loads(d.get("tags") or "[]")
            result.append(d)
        return result

    def update_task(self, tid: str, **fields: Any) -> dict[str, Any] | None:
        allowed = {"title", "notes", "status", "priority", "due_date", "tags"}
        updates = {k: v for k, v in fields.items() if k in allowed and v is not None}
        if not updates:
            return None
        if "tags" in updates and isinstance(updates["tags"], list):
            updates["tags"] = json.dumps(updates["tags"])
        updates["updated_at"] = utc_now()
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        values = list(updates.values()) + [tid]
        with self.connect() as conn:
            conn.execute(f"UPDATE tasks SET {set_clause} WHERE id = ?", values)
            row = conn.execute("SELECT * FROM tasks WHERE id = ?", (tid,)).fetchone()
        if not row:
            return None
        d = dict(row)
        d["tags"] = json.loads(d.get("tags") or "[]")
        return d

    def delete_task(self, tid: str) -> bool:
        with self.connect() as conn:
            cur = conn.execute("DELETE FROM tasks WHERE id = ?", (tid,))
            return cur.rowcount > 0

    # ---------------- Notes ----------------
    def create_note(
        self, title: str, content: str, tags: list[str] | None = None, pinned: bool = False
    ) -> dict[str, Any]:
        nid = str(uuid.uuid4())[:8]
        now = utc_now()
        tags_list = tags or []
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO notes (id, title, content, tags, pinned, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (nid, title, content, json.dumps(tags_list), int(pinned), now, now),
            )
        return {
            "id": nid,
            "title": title,
            "content": content,
            "tags": tags_list,
            "pinned": bool(pinned),
            "created_at": now,
            "updated_at": now,
        }

    def list_notes(self, query: str = "") -> list[dict[str, Any]]:
        with self.connect() as conn:
            if query.strip():
                like = f"%{query.strip()}%"
                rows = conn.execute(
                    """
                    SELECT * FROM notes
                    WHERE title LIKE ? OR content LIKE ? OR tags LIKE ?
                    ORDER BY pinned DESC, updated_at DESC
                    """,
                    (like, like, like),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM notes ORDER BY pinned DESC, updated_at DESC"
                ).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            d["tags"] = json.loads(d.get("tags") or "[]")
            d["pinned"] = bool(d["pinned"])
            out.append(d)
        return out

    def update_note(self, nid: str, **fields: Any) -> dict[str, Any] | None:
        allowed = {"title", "content", "tags", "pinned"}
        updates = {k: v for k, v in fields.items() if k in allowed and v is not None}
        if not updates:
            return None
        if "tags" in updates and isinstance(updates["tags"], list):
            updates["tags"] = json.dumps(updates["tags"])
        if "pinned" in updates:
            updates["pinned"] = int(bool(updates["pinned"]))
        updates["updated_at"] = utc_now()
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        with self.connect() as conn:
            conn.execute(f"UPDATE notes SET {set_clause} WHERE id = ?", list(updates.values()) + [nid])
            row = conn.execute("SELECT * FROM notes WHERE id = ?", (nid,)).fetchone()
        if not row:
            return None
        d = dict(row)
        d["tags"] = json.loads(d.get("tags") or "[]")
        d["pinned"] = bool(d["pinned"])
        return d

    def delete_note(self, nid: str) -> bool:
        with self.connect() as conn:
            cur = conn.execute("DELETE FROM notes WHERE id = ?", (nid,))
            return cur.rowcount > 0

    # ---------------- Reminders ----------------
    def create_reminder(self, title: str, remind_at: str, repeat: str = "none") -> dict[str, Any]:
        rid = str(uuid.uuid4())[:8]
        now = utc_now()
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO reminders (id, title, remind_at, repeat, triggered, created_at)
                VALUES (?, ?, ?, ?, 0, ?)
                """,
                (rid, title, remind_at, repeat, now),
            )
        return {
            "id": rid,
            "title": title,
            "remind_at": remind_at,
            "repeat": repeat,
            "triggered": False,
            "created_at": now,
        }

    def list_reminders(self, include_triggered: bool = True) -> list[dict[str, Any]]:
        with self.connect() as conn:
            if include_triggered:
                rows = conn.execute("SELECT * FROM reminders ORDER BY remind_at ASC").fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM reminders WHERE triggered = 0 ORDER BY remind_at ASC"
                ).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            d["triggered"] = bool(d["triggered"])
            out.append(d)
        return out

    def mark_reminder_triggered(self, rid: str) -> None:
        with self.connect() as conn:
            conn.execute("UPDATE reminders SET triggered = 1 WHERE id = ?", (rid,))

    def delete_reminder(self, rid: str) -> bool:
        with self.connect() as conn:
            cur = conn.execute("DELETE FROM reminders WHERE id = ?", (rid,))
            return cur.rowcount > 0

    # ---------------- Audit Log ----------------
    def log_audit(
        self, tool_name: str, tier: int, summary: str, details: dict[str, Any], status: str
    ) -> dict[str, Any]:
        aid = str(uuid.uuid4())[:8]
        now = utc_now()
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO audit_log (id, timestamp, tool_name, tier, summary, details, status)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (aid, now, tool_name, tier, summary, json.dumps(details), status),
            )
        return {
            "id": aid,
            "timestamp": now,
            "tool_name": tool_name,
            "tier": tier,
            "summary": summary,
            "details": details,
            "status": status,
        }

    def list_audit(self, limit: int = 50) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM audit_log ORDER BY timestamp DESC LIMIT ?", (limit,)
            ).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            d["details"] = json.loads(d.get("details") or "{}")
            out.append(d)
        return out


db = Database()
