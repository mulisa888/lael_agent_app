from __future__ import annotations

import json
import sys
from pathlib import Path

from fastapi.testclient import TestClient

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.main import app  # noqa: E402
from app.tools.registry import tool_registry  # noqa: E402

client = TestClient(app)


def test_health_and_customization():
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["ok"] is True

    orig = client.get("/api/settings").json()
    try:
        patched = client.patch(
            "/api/settings",
            json={
                "identity": {"name": "Lael Prime", "user_name": "Alex"},
                "appearance": {"theme": "aurora", "accent_color": "#10b981"},
            },
        ).json()
        assert patched["identity"]["name"] == "Lael Prime"
        assert patched["identity"]["user_name"] == "Alex"
        assert patched["appearance"]["theme"] == "aurora"
        assert patched["appearance"]["accent_color"] == "#10b981"
    finally:
        client.patch("/api/settings", json={"identity": orig["identity"], "appearance": orig["appearance"]})


def test_productivity_crud():
    # Tasks
    t = client.post("/api/tasks", json={"title": "Test Lael task", "priority": "high"}).json()
    assert t["title"] == "Test Lael task"
    upd = client.patch(f"/api/tasks/{t['id']}", json={"status": "done"}).json()
    assert upd["status"] == "done"
    assert client.delete(f"/api/tasks/{t['id']}").json()["ok"] is True

    # Notes
    n = client.post("/api/notes", json={"title": "Project Ideas", "content": "Build Lael desktop voice UI"}).json()
    found = client.get("/api/notes?q=voice").json()
    assert any(item["id"] == n["id"] for item in found)
    assert client.delete(f"/api/notes/{n['id']}").json()["ok"] is True

    # Reminders
    rem = client.post(
        "/api/reminders",
        json={"title": "Standup", "remind_at": "2099-01-01T09:00:00", "repeat": "none"},
    ).json()
    assert rem["title"] == "Standup"
    assert client.delete(f"/api/reminders/{rem['id']}").json()["ok"] is True


def test_knowledge_base_index_and_search(tmp_path: Path):
    doc = tmp_path / "lael_architecture.md"
    doc.write_text("Lael uses SQLite FTS5 for super fast offline document Q&A with citations.", encoding="utf-8")

    orig_folders = client.get("/api/settings").json()["knowledge_base"]["folders"]
    try:
        res = client.post("/api/kb/folders", json={"folder": str(tmp_path)})
        assert res.status_code == 200
        assert res.json()["index_result"]["indexed_files"] >= 1

        search = client.get("/api/kb/search?q=FTS5+citations").json()
        assert len(search["matches"]) >= 1
        assert search["matches"][0]["file_name"] == "lael_architecture.md"
    finally:
        client.patch("/api/settings", json={"knowledge_base": {"folders": orig_folders}})
        client.post("/api/kb/reindex")


def test_tier3_powershell_requires_approval():
    import asyncio

    res = asyncio.run(tool_registry.execute("run_powershell_command", {"command": "Write-Output 'hello'"}))
    assert res["ok"] is False
    assert res["status"] == "approval_required"
    approval_id = res["approval_id"]

    pending = client.get("/api/approvals").json()
    assert any(p["id"] == approval_id for p in pending)

    denied = client.post(f"/api/approvals/{approval_id}", json={"approved": False}).json()
    assert denied["ok"] is True
    assert denied["status"] == "denied"


def test_google_credentials_validation():
    bad = client.post("/api/google/credentials", json={"credentials_json": '{"not_valid": true}'}).json()
    assert bad["ok"] is False
    status = client.get("/api/google/status").json()
    assert "connected" in status
