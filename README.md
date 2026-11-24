# Lael — Customizable Windows Desktop & Voice Personal Assistant

**Lael** is a local-first Windows desktop & voice personal assistant built with **FastAPI + SQLite + React + TypeScript**, designed to be deeply customizable and switchable between **Local Ollama** and **Cloud Gemini API** (or any OpenAI-compatible API).

## Features
- **Voice & Chat Assistant**: Click the reactive Voice Orb to speak via Windows microphone (Web Speech API) and listen to spoken replies (Edge Natural Neural Voices or offline Windows SAPI).
- **Switchable AI Engine**: Toggle live between **Local Ollama** (`localhost:11434`), **Cloud Gemini API**, and **OpenAI-compatible** providers right from the top bar or Settings.
- **Deep Customization Studio**:
  - Rename assistant, set your name, greeting, tone, and full system persona prompt.
  - 5 built-in themes (`Midnight`, `Aurora`, `Obsidian`, `Forest`, `Daylight`), custom accent/glow hex pickers, 4 Voice Orb styles, density, font scale, and glass blur toggles.
  - Custom home Quick Action buttons, custom Daily Briefing city/news topics, and custom Windows app aliases.
- **Tasks, Notes & Reminders**: Stored locally in SQLite with a background daemon that fires native Windows desktop notifications.
- **Personal Knowledge Base (Document Q&A)**: Index local folders (`.txt`, `.md`, `.pdf`, `.docx`, `.csv`, `.json`, source code) into SQLite FTS5 for instant cited answers.
- **Daily Briefing & Web Search**: Combines live weather (Open-Meteo), curated web headlines (DuckDuckGo), open tasks, reminders, and Google Calendar/Gmail highlights.
- **Windows Automation with Tier 3 Safety Guardrails**: System telemetry, quick app launchers, clipboard tools, and PowerShell execution gated behind an explicit **Approve / Deny** modal + audit log.
- **Google Calendar & Gmail Integration**: Built-in zero-dependency OAuth 2.0 PKCE connector ready in **Settings -> Google Workspace**.

## Quick Start
Double-click `launch.bat` in the project root (`C:\Users\mulis\.gemini\antigravity\scratch\lael\launch.bat`).

Or run from PowerShell:
```powershell
cd C:\Users\mulis\.gemini\antigravity\scratch\lael\backend
.\.venv\Scripts\python.exe desktop.py
```

## Connecting Google Calendar & Gmail
1. In Google Cloud Console, enable **Google Calendar API** and **Gmail API**.
2. Create an **OAuth 2.0 Client ID** of type **Desktop app** and download the JSON file.
3. Open **Lael -> Customize -> Google Workspace**, paste the JSON, save it, and click **Connect Google Account**.
