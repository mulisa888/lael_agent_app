from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
SETTINGS_FILE = DATA_DIR / "settings.json"

DEFAULT_SETTINGS: dict[str, Any] = {
    "identity": {
        "name": "Lael",
        "user_name": "",
        "tagline": "Your personal desktop & voice assistant",
        "greeting": "Hi! I'm Lael. How can I help you organize your day?",
        "tone": "warm_concise",
        "system_prompt": (
            "You are Lael, a thoughtful, proactive, and highly capable personal desktop assistant "
            "running locally on the user's Windows PC. Be clear, warm, concise, and helpful. "
            "Use your tools whenever the user asks about their tasks, notes, reminders, local files, "
            "web search, daily briefing, Google Calendar/Gmail, or Windows system actions. "
            "Never fabricate tool results or file contents."
        ),
    },
    "appearance": {
        "theme": "midnight",
        "accent_color": "#7c5cff",
        "secondary_color": "#22d3ee",
        "orb_style": "aurora",
        "density": "comfortable",
        "glass_effects": True,
        "font_scale": 1.0,
    },
    "ai": {
        "provider": "ollama",
        "ollama_base_url": "http://127.0.0.1:11434",
        "ollama_model": "llama3.2",
        "gemini_api_key": "",
        "gemini_model": "gemini-2.5-flash",
        "openai_base_url": "https://api.openai.com/v1",
        "openai_api_key": "",
        "openai_model": "gpt-4o-mini",
        "temperature": 0.7,
        "max_tool_steps": 6,
    },
    "voice": {
        "enabled": True,
        "auto_speak": False,
        "tts_engine": "edge",
        "edge_voice": "en-US-AvaNeural",
        "rate": "+0%",
        "pitch": "+0Hz",
        "stt_language": "en-US",
    },
    "capabilities": {
        "tasks_notes_reminders": True,
        "knowledge_base": True,
        "web_search": True,
        "daily_briefing": True,
        "system_automation": True,
        "google_workspace": True,
    },
    "automation": {
        "allow_app_launch": True,
        "require_approval_for_shell": True,
        "allowed_apps": {
            "notepad": "notepad.exe",
            "calculator": "calc.exe",
            "explorer": "explorer.exe",
            "paint": "mspaint.exe",
            "edge": "msedge.exe",
            "chrome": "chrome.exe",
            "vscode": "code",
            "terminal": "wt.exe",
            "settings": "ms-settings:",
        },
    },
    "briefing": {
        "location": "New York",
        "topics": ["technology", "AI", "productivity"],
        "morning_time": "08:30",
        "include_weather": True,
        "include_news": True,
        "include_tasks": True,
        "include_google": True,
    },
    "knowledge_base": {
        "folders": [],
        "extensions": [".txt", ".md", ".pdf", ".docx", ".csv", ".json", ".py", ".ts", ".js"],
        "chunk_size": 900,
        "chunk_overlap": 150,
    },
    "quick_actions": [
        {
            "id": "briefing",
            "label": "Daily Briefing",
            "prompt": "Give me my daily briefing with today's tasks, reminders, weather, and top news.",
            "icon": "sun",
        },
        {
            "id": "tasks",
            "label": "Review My Tasks",
            "prompt": "List my open tasks and help me prioritize what to tackle first.",
            "icon": "check",
        },
        {
            "id": "docs",
            "label": "Search My Files",
            "prompt": "What documents do I currently have indexed in my knowledge base?",
            "icon": "folder",
        },
        {
            "id": "system",
            "label": "PC Health Check",
            "prompt": "Check my Windows system health (CPU, memory, disk, and battery).",
            "icon": "cpu",
        },
    ],
    "google": {
        "enabled": True,
        "calendar_enabled": True,
        "gmail_enabled": True,
        "credentials_file": str(DATA_DIR / "google_credentials.json"),
        "token_file": str(DATA_DIR / "google_token.json"),
    },
}


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = copy.deepcopy(base)
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(merged.get(k), dict):
            merged[k] = _deep_merge(merged[k], v)
        else:
            merged[k] = copy.deepcopy(v)
    return merged


class SettingsManager:
    def __init__(self, path: Path = SETTINGS_FILE) -> None:
        self.path = path
        self._settings = self._load()

    def _load(self) -> dict[str, Any]:
        if self.path.exists():
            try:
                raw = json.loads(self.path.read_text(encoding="utf-8"))
                return _deep_merge(DEFAULT_SETTINGS, raw)
            except Exception:
                return copy.deepcopy(DEFAULT_SETTINGS)
        data = copy.deepcopy(DEFAULT_SETTINGS)
        self._save(data)
        return data

    def _save(self, data: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def get(self) -> dict[str, Any]:
        return copy.deepcopy(self._settings)

    def update(self, patch: dict[str, Any]) -> dict[str, Any]:
        self._settings = _deep_merge(self._settings, patch)
        self._save(self._settings)
        return self.get()

    def reset(self) -> dict[str, Any]:
        self._settings = copy.deepcopy(DEFAULT_SETTINGS)
        self._save(self._settings)
        return self.get()

    def build_system_prompt(self) -> str:
        ident = self._settings["identity"]
        name = ident.get("name", "Lael")
        user_name = ident.get("user_name", "").strip()
        tone_map = {
            "warm_concise": "Use a warm, friendly, and concise conversational tone.",
            "professional": "Use a crisp, structured, executive-assistant tone.",
            "playful": "Use an upbeat, creative, witty tone while staying helpful.",
            "direct": "Be ultra-concise, direct, and bullet-focused.",
        }
        tone_inst = tone_map.get(ident.get("tone", "warm_concise"), "")
        base_prompt = ident.get("system_prompt", DEFAULT_SETTINGS["identity"]["system_prompt"])
        parts = [base_prompt.replace("Lael", name), tone_inst]
        if user_name:
            parts.append(f"The user's name is {user_name}. Address them naturally when appropriate.")
        return "\n".join(p for p in parts if p)


settings_manager = SettingsManager()
