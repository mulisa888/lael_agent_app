from __future__ import annotations

import asyncio
import json
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app.config import settings_manager
from app.database import db
from app.llm.router import llm_router
from app.scheduler import reminder_loop, send_windows_notification
from app.tools.google_conn import google_connector, register_google_tools
from app.tools.knowledge import index_folders, list_indexed_files, register_knowledge_tools, search_knowledge_base
from app.tools.productivity import register_productivity_tools
from app.tools.registry import tool_registry
from app.tools.system_auto import get_system_info, open_application, register_system_tools
from app.tools.web_briefing import build_daily_briefing, register_web_briefing_tools
from app.voice import list_windows_sapi_voices, synthesize_windows_sapi_wav

# Register all built-in modular tools
register_productivity_tools()
register_knowledge_tools()
register_web_briefing_tools()
register_system_tools()
register_google_tools()

FRONTEND_DIST = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"


@asynccontextmanager
async def lifespan(_app: FastAPI):
    stop_event = asyncio.Event()
    task = asyncio.create_task(reminder_loop(stop_event))
    yield
    stop_event.set()
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


app = FastAPI(title="Lael Personal Assistant API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# -------------------- Request Schemas --------------------
class ChatRequest(BaseModel):
    conversation_id: str | None = None
    message: str


class TaskCreate(BaseModel):
    title: str
    notes: str = ""
    priority: str = "medium"
    due_date: str = ""
    tags: list[str] = []


class TaskUpdate(BaseModel):
    title: str | None = None
    notes: str | None = None
    status: str | None = None
    priority: str | None = None
    due_date: str | None = None
    tags: list[str] | None = None


class NoteCreate(BaseModel):
    title: str
    content: str
    tags: list[str] = []
    pinned: bool = False


class NoteUpdate(BaseModel):
    title: str | None = None
    content: str | None = None
    tags: list[str] | None = None
    pinned: bool | None = None


class ReminderCreate(BaseModel):
    title: str
    remind_at: str
    repeat: str = "none"


class FolderPayload(BaseModel):
    folder: str


class ApprovalDecision(BaseModel):
    approved: bool


class SpeakRequest(BaseModel):
    text: str
    voice: str = ""
    rate: int = 0


class GoogleCredsPayload(BaseModel):
    credentials_json: str


# -------------------- Health & Settings --------------------
@app.get("/api/health")
async def health() -> dict[str, Any]:
    cfg = settings_manager.get()
    return {
        "ok": True,
        "name": cfg["identity"]["name"],
        "provider": cfg["ai"]["provider"],
        "time": datetime.now().isoformat(),
    }


@app.get("/api/settings")
async def get_settings() -> dict[str, Any]:
    return settings_manager.get()


@app.patch("/api/settings")
async def update_settings(patch: dict[str, Any]) -> dict[str, Any]:
    return settings_manager.update(patch)


@app.post("/api/settings/reset")
async def reset_settings() -> dict[str, Any]:
    return settings_manager.reset()


@app.get("/api/providers/ollama/models")
async def ollama_models() -> dict[str, Any]:
    base_url = settings_manager.get()["ai"].get("ollama_base_url", "http://127.0.0.1:11434")
    return await llm_router.list_ollama_models(base_url)


@app.get("/api/tools")
async def list_tools() -> dict[str, Any]:
    return {"tools": tool_registry.list_all_metadata()}


# -------------------- Conversations & Agent Chat --------------------
@app.get("/api/conversations")
async def list_conversations() -> list[dict[str, Any]]:
    return db.list_conversations()


@app.post("/api/conversations")
async def create_conversation(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    title = (payload or {}).get("title") or "New Chat"
    return db.create_conversation(title=title)


@app.get("/api/conversations/{cid}")
async def get_conversation_detail(cid: str) -> dict[str, Any]:
    conv = db.get_conversation(cid)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return {"conversation": conv, "messages": db.get_messages(cid)}


@app.delete("/api/conversations/{cid}")
async def delete_conversation(cid: str) -> dict[str, Any]:
    db.delete_conversation(cid)
    return {"ok": True}


@app.post("/api/chat")
async def chat_endpoint(req: ChatRequest) -> dict[str, Any]:
    user_text = req.message.strip()
    if not user_text:
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    cid = req.conversation_id
    if not cid or not db.get_conversation(cid):
        title = user_text[:50] + ("..." if len(user_text) > 50 else "")
        conv = db.create_conversation(title=title)
        cid = conv["id"]
    else:
        existing = db.get_messages(cid, limit=1)
        if not existing:
            db.rename_conversation(cid, user_text[:50] + ("..." if len(user_text) > 50 else ""))

    db.add_message(cid, "user", user_text)

    cfg = settings_manager.get()
    ai_cfg = cfg["ai"]
    max_steps = int(ai_cfg.get("max_tool_steps", 6))
    tools = tool_registry.list_enabled_schemas()

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S (%A)")
    sys_prompt = (
        settings_manager.build_system_prompt()
        + f"\nCurrent local Windows date & time: {now_str}."
        + "\nWhen a tool returns 'approval_required', clearly explain the pending action so the user can approve or deny it."
    )

    history = db.get_messages(cid, limit=24)
    llm_messages: list[dict[str, Any]] = [{"role": "system", "content": sys_prompt}]
    for h in history:
        if h["role"] in ("user", "assistant"):
            llm_messages.append({"role": h["role"], "content": h["content"]})

    tool_events: list[dict[str, Any]] = []
    final_content = ""
    used_provider = ai_cfg.get("provider", "ollama")
    used_model = ""

    for _step in range(max_steps):
        res = await llm_router.chat(ai_cfg=ai_cfg, messages=llm_messages, tools=tools)
        used_provider = res.provider or used_provider
        used_model = res.model or used_model

        if res.error:
            final_content = f"**Model Connection Notice:** {res.error}"
            break

        if not res.tool_calls:
            final_content = res.content or "Done."
            break

        # Append assistant message with tool_calls
        llm_messages.append(
            {
                "role": "assistant",
                "content": res.content or "",
                "tool_calls": [
                    {"id": tc.id, "function": {"name": tc.name, "arguments": tc.arguments}}
                    for tc in res.tool_calls
                ],
            }
        )

        for tc in res.tool_calls:
            result = await tool_registry.execute(tc.name, tc.arguments)
            tool_events.append(
                {
                    "tool": tc.name,
                    "arguments": tc.arguments,
                    "result": result,
                }
            )
            llm_messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "name": tc.name,
                    "content": json.dumps(result, default=str)[:8000],
                }
            )
    else:
        final_content = "I ran multiple tool steps to gather information. Let me know if you'd like me to continue."

    assistant_msg = db.add_message(
        cid,
        "assistant",
        final_content,
        tool_events=tool_events,
        provider=used_provider,
        model=used_model,
    )
    return {
        "conversation_id": cid,
        "message": assistant_msg,
        "pending_approvals": tool_registry.list_pending_approvals(),
    }


# -------------------- Tasks, Notes, Reminders --------------------
@app.get("/api/tasks")
async def get_tasks(status: str = "all") -> list[dict[str, Any]]:
    return db.list_tasks(status=status)


@app.post("/api/tasks")
async def create_task_api(payload: TaskCreate) -> dict[str, Any]:
    return db.create_task(**payload.model_dump())


@app.patch("/api/tasks/{tid}")
async def update_task_api(tid: str, payload: TaskUpdate) -> dict[str, Any]:
    updated = db.update_task(tid, **payload.model_dump())
    if not updated:
        raise HTTPException(status_code=404, detail="Task not found")
    return updated


@app.delete("/api/tasks/{tid}")
async def delete_task_api(tid: str) -> dict[str, Any]:
    return {"ok": db.delete_task(tid)}


@app.get("/api/notes")
async def get_notes(q: str = "") -> list[dict[str, Any]]:
    return db.list_notes(query=q)


@app.post("/api/notes")
async def create_note_api(payload: NoteCreate) -> dict[str, Any]:
    return db.create_note(**payload.model_dump())


@app.patch("/api/notes/{nid}")
async def update_note_api(nid: str, payload: NoteUpdate) -> dict[str, Any]:
    updated = db.update_note(nid, **payload.model_dump())
    if not updated:
        raise HTTPException(status_code=404, detail="Note not found")
    return updated


@app.delete("/api/notes/{nid}")
async def delete_note_api(nid: str) -> dict[str, Any]:
    return {"ok": db.delete_note(nid)}


@app.get("/api/reminders")
async def get_reminders() -> list[dict[str, Any]]:
    return db.list_reminders(include_triggered=True)


@app.post("/api/reminders")
async def create_reminder_api(payload: ReminderCreate) -> dict[str, Any]:
    return db.create_reminder(**payload.model_dump())


@app.delete("/api/reminders/{rid}")
async def delete_reminder_api(rid: str) -> dict[str, Any]:
    return {"ok": db.delete_reminder(rid)}


@app.post("/api/reminders/test-notification")
async def test_notification() -> dict[str, Any]:
    name = settings_manager.get()["identity"].get("name", "Lael")
    asyncio.create_task(send_windows_notification(f"{name} Notification Test", "Desktop reminders are active!"))
    return {"ok": True}


# -------------------- Knowledge Base --------------------
@app.get("/api/kb/files")
async def kb_files() -> dict[str, Any]:
    cfg = settings_manager.get()["knowledge_base"]
    return {"folders": cfg.get("folders", []), "extensions": cfg.get("extensions", []), "files": list_indexed_files()}


@app.post("/api/kb/folders")
async def kb_add_folder(payload: FolderPayload) -> dict[str, Any]:
    folder = payload.folder.strip()
    if not folder:
        raise HTTPException(status_code=400, detail="Folder path is required")
    cfg = settings_manager.get()
    folders = list(cfg["knowledge_base"].get("folders", []))
    if folder not in folders:
        folders.append(folder)
        settings_manager.update({"knowledge_base": {"folders": folders}})
    result = await asyncio.to_thread(index_folders)
    return {"folders": folders, "index_result": result}


@app.delete("/api/kb/folders")
async def kb_remove_folder(folder: str) -> dict[str, Any]:
    cfg = settings_manager.get()
    folders = [f for f in cfg["knowledge_base"].get("folders", []) if f != folder]
    settings_manager.update({"knowledge_base": {"folders": folders}})
    result = await asyncio.to_thread(index_folders)
    return {"folders": folders, "index_result": result}


@app.post("/api/kb/reindex")
async def kb_reindex() -> dict[str, Any]:
    return await asyncio.to_thread(index_folders)


@app.get("/api/kb/search")
async def kb_search(q: str, limit: int = 6) -> dict[str, Any]:
    return {"query": q, "matches": search_knowledge_base(q, limit=limit)}


# -------------------- Briefing & System & Approvals --------------------
@app.get("/api/briefing")
async def daily_briefing_api() -> dict[str, Any]:
    return await build_daily_briefing()


@app.get("/api/system/info")
async def system_info_api() -> dict[str, Any]:
    return await get_system_info()


@app.post("/api/system/open-app")
async def open_app_api(payload: dict[str, str]) -> dict[str, Any]:
    return await open_application(payload.get("app_name", ""))


@app.get("/api/approvals")
async def get_approvals() -> list[dict[str, Any]]:
    return tool_registry.list_pending_approvals()


@app.post("/api/approvals/{approval_id}")
async def resolve_approval(approval_id: str, decision: ApprovalDecision) -> dict[str, Any]:
    return await tool_registry.resolve_approval(approval_id, approved=decision.approved)


@app.get("/api/audit")
async def get_audit(limit: int = 50) -> list[dict[str, Any]]:
    return db.list_audit(limit=limit)


# -------------------- Voice (Windows SAPI Offline TTS) --------------------
@app.get("/api/voice/sapi-voices")
async def sapi_voices() -> dict[str, Any]:
    return {"voices": await list_windows_sapi_voices()}


@app.post("/api/voice/speak")
async def speak_sapi(req: SpeakRequest) -> Response:
    audio = await synthesize_windows_sapi_wav(req.text, voice_name=req.voice, rate=req.rate)
    if not audio:
        raise HTTPException(status_code=500, detail="Could not synthesize Windows SAPI audio")
    return Response(content=audio, media_type="audio/wav")


# -------------------- Google Workspace Connector --------------------
@app.get("/api/google/status")
async def google_status() -> dict[str, Any]:
    return google_connector.status()


@app.post("/api/google/credentials")
async def google_save_creds(payload: GoogleCredsPayload) -> dict[str, Any]:
    return google_connector.save_credentials_json(payload.credentials_json)


@app.post("/api/google/connect")
async def google_connect() -> dict[str, Any]:
    return await google_connector.connect_oauth()


@app.post("/api/google/disconnect")
async def google_disconnect() -> dict[str, Any]:
    return google_connector.disconnect()


@app.get("/api/google/summary")
async def google_summary() -> dict[str, Any]:
    status = google_connector.status()
    if not status.get("connected"):
        return {"connected": False, "events": [], "emails": []}
    events, emails = await asyncio.gather(
        google_connector.list_upcoming_events(max_results=6),
        google_connector.list_recent_emails(max_results=6),
    )
    return {
        "connected": True,
        "events": events.get("events", []),
        "emails": emails.get("emails", []),
    }


# -------------------- Frontend Static Serving --------------------
if FRONTEND_DIST.exists():
    assets_dir = FRONTEND_DIST / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        if full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="API route not found")
        candidate = FRONTEND_DIST / full_path
        if full_path and candidate.is_file():
            return FileResponse(str(candidate))
        return FileResponse(str(FRONTEND_DIST / "index.html"))
