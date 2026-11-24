from __future__ import annotations

import html
import re
from datetime import datetime
from typing import Any
from urllib.parse import unquote

import httpx

from app.config import settings_manager
from app.database import db
from app.tools.registry import ToolDef, tool_registry

WEATHER_CODES = {
    0: "Clear sky",
    1: "Mainly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Fog",
    48: "Rime fog",
    51: "Light drizzle",
    53: "Drizzle",
    55: "Heavy drizzle",
    61: "Light rain",
    63: "Rain",
    65: "Heavy rain",
    71: "Light snow",
    73: "Snow",
    75: "Heavy snow",
    80: "Rain showers",
    95: "Thunderstorm",
}


async def web_search(query: str, max_results: int = 5) -> dict[str, Any]:
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0 Safari/537.36"
    }
    results: list[dict[str, str]] = []
    try:
        async with httpx.AsyncClient(timeout=12.0, follow_redirects=True, headers=headers) as client:
            resp = await client.post("https://html.duckduckgo.com/html/", data={"q": query})
            resp.raise_for_status()
            body = resp.text

        # Parse result blocks cleanly without extra HTML parser deps
        links = re.findall(
            r'<a[^>]*class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>',
            body,
            flags=re.S | re.I,
        )
        snippets = re.findall(
            r'<a[^>]*class="result__snippet"[^>]*>(.*?)</a>|<div[^>]*class="result__snippet"[^>]*>(.*?)</div>',
            body,
            flags=re.S | re.I,
        )
        for idx, (href, raw_title) in enumerate(links[:max_results]):
            title = html.unescape(re.sub(r"<[^>]+>", "", raw_title)).strip()
            snippet_raw = ""
            if idx < len(snippets):
                snippet_raw = snippets[idx][0] or snippets[idx][1]
            snippet = html.unescape(re.sub(r"<[^>]+>", "", snippet_raw)).strip()
            url = href
            if "uddg=" in href:
                m = re.search(r"uddg=([^&]+)", href)
                if m:
                    url = unquote(m.group(1))
            results.append({"title": title, "url": url, "snippet": snippet})
        return {"ok": True, "query": query, "results": results}
    except Exception as exc:
        return {"ok": False, "query": query, "results": [], "error": f"Web search unavailable: {exc}"}


async def get_weather(location: str) -> dict[str, Any]:
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            geo = await client.get(
                "https://geocoding-api.open-meteo.com/v1/search",
                params={"name": location, "count": 1, "language": "en", "format": "json"},
            )
            geo.raise_for_status()
            places = geo.json().get("results") or []
            if not places:
                return {"ok": False, "error": f"Could not find location '{location}'."}
            place = places[0]
            lat, lon = place["latitude"], place["longitude"]
            fc = await client.get(
                "https://api.open-meteo.com/v1/forecast",
                params={
                    "latitude": lat,
                    "longitude": lon,
                    "current": "temperature_2m,apparent_temperature,weather_code,wind_speed_10m",
                    "daily": "temperature_2m_max,temperature_2m_min,precipitation_probability_max",
                    "timezone": "auto",
                    "forecast_days": 1,
                },
            )
            fc.raise_for_status()
            data = fc.json()
            cur = data.get("current", {})
            daily = data.get("daily", {})
            code = int(cur.get("weather_code", 0))
            return {
                "ok": True,
                "location": f"{place.get('name')}, {place.get('country', '')}".strip(", "),
                "temperature_c": cur.get("temperature_2m"),
                "feels_like_c": cur.get("apparent_temperature"),
                "condition": WEATHER_CODES.get(code, f"Code {code}"),
                "wind_kmh": cur.get("wind_speed_10m"),
                "high_c": (daily.get("temperature_2m_max") or [None])[0],
                "low_c": (daily.get("temperature_2m_min") or [None])[0],
                "rain_chance_pct": (daily.get("precipitation_probability_max") or [None])[0],
            }
    except Exception as exc:
        return {"ok": False, "error": f"Weather unavailable: {exc}"}


async def build_daily_briefing() -> dict[str, Any]:
    cfg = settings_manager.get()
    briefing_cfg = cfg.get("briefing", {})
    ident = cfg.get("identity", {})
    now = datetime.now()
    hour = now.hour
    salutation = "Good morning" if hour < 12 else ("Good afternoon" if hour < 18 else "Good evening")
    user_name = ident.get("user_name", "").strip()
    greeting = f"{salutation}{', ' + user_name if user_name else ''}!"

    open_tasks = db.list_tasks(status="open") if briefing_cfg.get("include_tasks", True) else []
    reminders = db.list_reminders(include_triggered=False)

    weather = None
    if briefing_cfg.get("include_weather", True):
        weather = await get_weather(briefing_cfg.get("location", "New York"))

    news: list[dict[str, Any]] = []
    if briefing_cfg.get("include_news", True):
        topics = briefing_cfg.get("topics") or ["technology"]
        for topic in topics[:3]:
            res = await web_search(f"{topic} latest news today", max_results=2)
            if res.get("ok"):
                for item in res["results"]:
                    news.append({"topic": topic, **item})

    google_summary: dict[str, Any] = {"connected": False}
    if briefing_cfg.get("include_google", True):
        from app.tools.google_conn import google_connector

        status = google_connector.status()
        if status.get("connected"):
            events = await google_connector.list_upcoming_events(max_results=5)
            emails = await google_connector.list_recent_emails(max_results=5)
            google_summary = {
                "connected": True,
                "events": events.get("events", []),
                "emails": emails.get("emails", []),
            }

    return {
        "ok": True,
        "generated_at": now.isoformat(),
        "date_label": now.strftime("%A, %B %d, %Y"),
        "greeting": greeting,
        "weather": weather,
        "tasks": open_tasks[:10],
        "reminders": reminders[:10],
        "news": news[:6],
        "google": google_summary,
    }


async def _tool_web_search(args: dict[str, Any]) -> dict[str, Any]:
    q = (args.get("query") or "").strip()
    if not q:
        return {"ok": False, "error": "Query is required."}
    return await web_search(q, max_results=int(args.get("max_results", 5)))


async def _tool_get_weather(args: dict[str, Any]) -> dict[str, Any]:
    loc = (args.get("location") or "").strip() or settings_manager.get()["briefing"].get("location", "New York")
    return await get_weather(loc)


async def _tool_daily_briefing(args: dict[str, Any]) -> dict[str, Any]:
    return await build_daily_briefing()


def register_web_briefing_tools() -> None:
    tool_registry.register(
        ToolDef(
            name="web_search",
            description="Search the live web for up-to-date facts, news, or answers.",
            parameters={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                    "max_results": {"type": "integer", "description": "Max results (default 5)"},
                },
                "required": ["query"],
            },
            category="web_search",
            tier=1,
            handler=_tool_web_search,
        )
    )
    tool_registry.register(
        ToolDef(
            name="get_weather",
            description="Get current weather and today's forecast for a city.",
            parameters={
                "type": "object",
                "properties": {"location": {"type": "string", "description": "City name (defaults to user's configured briefing city)"}},
            },
            category="daily_briefing",
            tier=1,
            handler=_tool_get_weather,
        )
    )
    tool_registry.register(
        ToolDef(
            name="get_daily_briefing",
            description="Compile the user's personalized daily briefing (tasks, reminders, weather, news, and Google Calendar/Gmail if connected).",
            parameters={"type": "object", "properties": {}},
            category="daily_briefing",
            tier=1,
            handler=_tool_daily_briefing,
        )
    )
