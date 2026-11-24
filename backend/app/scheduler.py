from __future__ import annotations

import asyncio
from datetime import datetime, timedelta

from app.config import settings_manager
from app.database import db


async def send_windows_notification(title: str, message: str) -> None:
    """Show a native Windows desktop balloon/toast notification via PowerShell."""
    safe_title = title.replace("'", "''")[:80]
    safe_msg = message.replace("'", "''")[:240]
    ps = f"""
    Add-Type -AssemblyName System.Windows.Forms
    Add-Type -AssemblyName System.Drawing
    $n = New-Object System.Windows.Forms.NotifyIcon
    $n.Icon = [System.Drawing.SystemIcons]::Information
    $n.BalloonTipTitle = '{safe_title}'
    $n.BalloonTipText = '{safe_msg}'
    $n.Visible = $true
    $n.ShowBalloonTip(5000)
    Start-Sleep -Milliseconds 5200
    $n.Dispose()
    """
    try:
        proc = await asyncio.create_subprocess_exec(
            "powershell",
            "-NoProfile",
            "-WindowStyle",
            "Hidden",
            "-Command",
            ps,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await asyncio.wait_for(proc.communicate(), timeout=12)
    except Exception:
        pass


async def reminder_loop(stop_event: asyncio.Event) -> None:
    while not stop_event.is_set():
        try:
            now = datetime.now()
            due = db.list_reminders(include_triggered=False)
            assistant_name = settings_manager.get()["identity"].get("name", "Lael")
            for rem in due:
                try:
                    target = datetime.fromisoformat(rem["remind_at"].replace("Z", "+00:00"))
                    if target.tzinfo is not None:
                        target = target.astimezone().replace(tzinfo=None)
                except Exception:
                    continue
                if target <= now:
                    db.mark_reminder_triggered(rem["id"])
                    asyncio.create_task(send_windows_notification(f"{assistant_name} Reminder", rem["title"]))
                    repeat = rem.get("repeat", "none")
                    if repeat == "daily":
                        next_time = (target + timedelta(days=1)).isoformat(timespec="seconds")
                        db.create_reminder(rem["title"], next_time, repeat="daily")
                    elif repeat == "weekly":
                        next_time = (target + timedelta(weeks=1)).isoformat(timespec="seconds")
                        db.create_reminder(rem["title"], next_time, repeat="weekly")
        except Exception:
            pass

        try:
            await asyncio.wait_for(stop_event.wait(), timeout=20.0)
        except asyncio.TimeoutError:
            continue
