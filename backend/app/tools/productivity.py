from __future__ import annotations

from typing import Any

from app.database import db
from app.tools.registry import ToolDef, tool_registry


async def _list_tasks(args: dict[str, Any]) -> dict[str, Any]:
    status = args.get("status", "open")
    tasks = db.list_tasks(status=status)
    return {"ok": True, "count": len(tasks), "tasks": tasks}


async def _create_task(args: dict[str, Any]) -> dict[str, Any]:
    title = (args.get("title") or "").strip()
    if not title:
        return {"ok": False, "error": "Task title is required."}
    task = db.create_task(
        title=title,
        notes=args.get("notes", ""),
        priority=args.get("priority", "medium"),
        due_date=args.get("due_date", ""),
        tags=args.get("tags") or [],
    )
    return {"ok": True, "task": task}


async def _update_task(args: dict[str, Any]) -> dict[str, Any]:
    tid = (args.get("task_id") or "").strip()
    if not tid:
        return {"ok": False, "error": "task_id is required."}
    task = db.update_task(
        tid,
        title=args.get("title"),
        notes=args.get("notes"),
        status=args.get("status"),
        priority=args.get("priority"),
        due_date=args.get("due_date"),
    )
    if not task:
        return {"ok": False, "error": f"Task '{tid}' not found."}
    return {"ok": True, "task": task}


async def _create_note(args: dict[str, Any]) -> dict[str, Any]:
    title = (args.get("title") or "").strip() or "Untitled Note"
    content = (args.get("content") or "").strip()
    note = db.create_note(title=title, content=content, tags=args.get("tags") or [], pinned=bool(args.get("pinned", False)))
    return {"ok": True, "note": note}


async def _search_notes(args: dict[str, Any]) -> dict[str, Any]:
    query = args.get("query", "")
    notes = db.list_notes(query=query)
    return {"ok": True, "count": len(notes), "notes": notes}


async def _create_reminder(args: dict[str, Any]) -> dict[str, Any]:
    title = (args.get("title") or "").strip()
    remind_at = (args.get("remind_at") or "").strip()
    if not title or not remind_at:
        return {"ok": False, "error": "Both 'title' and 'remind_at' (ISO datetime like 2026-11-24T18:30:00) are required."}
    rem = db.create_reminder(title=title, remind_at=remind_at, repeat=args.get("repeat", "none"))
    return {"ok": True, "reminder": rem}


async def _list_reminders(args: dict[str, Any]) -> dict[str, Any]:
    rems = db.list_reminders(include_triggered=bool(args.get("include_triggered", False)))
    return {"ok": True, "count": len(rems), "reminders": rems}


def register_productivity_tools() -> None:
    tool_registry.register(
        ToolDef(
            name="list_tasks",
            description="List the user's tasks filtered by status ('open', 'done', or 'all').",
            parameters={
                "type": "object",
                "properties": {
                    "status": {"type": "string", "enum": ["open", "done", "all"], "description": "Filter by status"}
                },
            },
            category="tasks_notes_reminders",
            tier=1,
            handler=_list_tasks,
        )
    )
    tool_registry.register(
        ToolDef(
            name="create_task",
            description="Create a new personal task or to-do item.",
            parameters={
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "Short task title"},
                    "notes": {"type": "string", "description": "Optional details"},
                    "priority": {"type": "string", "enum": ["low", "medium", "high"]},
                    "due_date": {"type": "string", "description": "Optional YYYY-MM-DD due date"},
                },
                "required": ["title"],
            },
            category="tasks_notes_reminders",
            tier=2,
            handler=_create_task,
        )
    )
    tool_registry.register(
        ToolDef(
            name="update_task",
            description="Update a task's status ('open' or 'done'), priority, title, notes, or due_date.",
            parameters={
                "type": "object",
                "properties": {
                    "task_id": {"type": "string"},
                    "status": {"type": "string", "enum": ["open", "done"]},
                    "priority": {"type": "string", "enum": ["low", "medium", "high"]},
                    "title": {"type": "string"},
                    "notes": {"type": "string"},
                    "due_date": {"type": "string"},
                },
                "required": ["task_id"],
            },
            category="tasks_notes_reminders",
            tier=2,
            handler=_update_task,
        )
    )
    tool_registry.register(
        ToolDef(
            name="create_note",
            description="Save a personal note to the local database.",
            parameters={
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "content": {"type": "string"},
                    "tags": {"type": "array", "items": {"type": "string"}},
                    "pinned": {"type": "boolean"},
                },
                "required": ["title", "content"],
            },
            category="tasks_notes_reminders",
            tier=2,
            handler=_create_note,
        )
    )
    tool_registry.register(
        ToolDef(
            name="search_notes",
            description="Search or list personal notes. Leave query empty to list all notes.",
            parameters={
                "type": "object",
                "properties": {"query": {"type": "string", "description": "Keyword to search in title/content/tags"}},
            },
            category="tasks_notes_reminders",
            tier=1,
            handler=_search_notes,
        )
    )
    tool_registry.register(
        ToolDef(
            name="create_reminder",
            description="Schedule a desktop reminder notification at a specific local ISO datetime (e.g., 2026-11-24T19:00:00).",
            parameters={
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "What to remind the user about"},
                    "remind_at": {"type": "string", "description": "Local ISO-8601 datetime YYYY-MM-DDTHH:MM:SS"},
                    "repeat": {"type": "string", "enum": ["none", "daily", "weekly"]},
                },
                "required": ["title", "remind_at"],
            },
            category="tasks_notes_reminders",
            tier=2,
            handler=_create_reminder,
        )
    )
    tool_registry.register(
        ToolDef(
            name="list_reminders",
            description="List upcoming or past reminders.",
            parameters={
                "type": "object",
                "properties": {"include_triggered": {"type": "boolean"}},
            },
            category="tasks_notes_reminders",
            tier=1,
            handler=_list_reminders,
        )
    )
