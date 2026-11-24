"""Windows Desktop Launcher for Lael Personal Assistant.

Starts the local FastAPI server and opens Lael in a standalone frameless
Windows app window (Edge/Chrome --app mode) with full microphone & voice support.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import threading
import time
import urllib.request
import webbrowser
from pathlib import Path

import uvicorn

HOST = "127.0.0.1"
PORT = int(os.environ.get("LAEL_PORT", "8765"))
URL = f"http://{HOST}:{PORT}"
PROFILE_DIR = Path(__file__).resolve().parent / "data" / "desktop_profile"


def find_chromium_browser() -> str | None:
    candidates = [
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    ]
    for path in candidates:
        if Path(path).exists():
            return path
    return shutil.which("msedge") or shutil.which("chrome")


def wait_for_server(timeout: float = 15.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(f"{URL}/api/health", timeout=1.5) as resp:
                if resp.status == 200:
                    return True
        except Exception:
            time.sleep(0.25)
    return False


def launch_desktop_window() -> None:
    if not wait_for_server():
        return
    browser = find_chromium_browser()
    if browser:
        PROFILE_DIR.mkdir(parents=True, exist_ok=True)
        subprocess.Popen(
            [
                browser,
                f"--app={URL}",
                f"--user-data-dir={PROFILE_DIR}",
                "--window-size=1280,820",
                "--disable-features=Translate",
            ]
        )
    else:
        webbrowser.open(URL)


def main() -> None:
    no_window = "--server-only" in sys.argv
    if not no_window:
        threading.Thread(target=launch_desktop_window, daemon=True).start()
    print(f"Lael Personal Assistant running at {URL}")
    uvicorn.run("app.main:app", host=HOST, port=PORT, log_level="info")


if __name__ == "__main__":
    main()
