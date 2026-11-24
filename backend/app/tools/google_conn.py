from __future__ import annotations

import asyncio
import base64
import hashlib
import http.server
import json
import secrets
import time
import urllib.parse
import webbrowser
from datetime import datetime, timezone
from email.message import EmailMessage
from pathlib import Path
from typing import Any

import httpx

from app.config import settings_manager
from app.tools.registry import ToolDef, tool_registry

SCOPES = [
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/calendar.events",
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
]


class GoogleConnector:
    """Zero-dependency OAuth 2.0 PKCE + REST connector for Google Calendar & Gmail."""

    def _paths(self) -> tuple[Path, Path]:
        gcfg = settings_manager.get().get("google", {})
        return Path(gcfg.get("credentials_file", "")), Path(gcfg.get("token_file", ""))

    def _read_client_config(self) -> dict[str, Any] | None:
        cred_path, _ = self._paths()
        if not cred_path.exists():
            return None
        try:
            raw = json.loads(cred_path.read_text(encoding="utf-8"))
            return raw.get("installed") or raw.get("web")
        except Exception:
            return None

    def _read_token(self) -> dict[str, Any] | None:
        _, token_path = self._paths()
        if not token_path.exists():
            return None
        try:
            return json.loads(token_path.read_text(encoding="utf-8"))
        except Exception:
            return None

    def _write_token(self, data: dict[str, Any]) -> None:
        _, token_path = self._paths()
        token_path.parent.mkdir(parents=True, exist_ok=True)
        token_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def status(self) -> dict[str, Any]:
        cred_path, token_path = self._paths()
        creds_found = self._read_client_config() is not None
        token = self._read_token()
        connected = bool(token and (token.get("access_token") or token.get("refresh_token")))
        return {
            "credentials_found": creds_found,
            "credentials_path": str(cred_path),
            "token_found": token_path.exists(),
            "connected": connected,
            "email": (token or {}).get("email", ""),
            "scopes": SCOPES,
        }

    def save_credentials_json(self, raw_json: str) -> dict[str, Any]:
        try:
            parsed = json.loads(raw_json)
            if "installed" not in parsed and "web" not in parsed:
                return {
                    "ok": False,
                    "error": "JSON must be a Google OAuth Desktop client file containing an 'installed' or 'web' key.",
                }
        except Exception as exc:
            return {"ok": False, "error": f"Invalid JSON: {exc}"}

        cred_path, _ = self._paths()
        cred_path.parent.mkdir(parents=True, exist_ok=True)
        cred_path.write_text(json.dumps(parsed, indent=2), encoding="utf-8")
        return {"ok": True, "path": str(cred_path)}

    async def _get_valid_token(self) -> str | None:
        token = self._read_token()
        if not token:
            return None
        expires_at = float(token.get("expires_at", 0))
        if token.get("access_token") and time.time() < expires_at - 60:
            return str(token["access_token"])

        refresh_token = token.get("refresh_token")
        client_cfg = self._read_client_config()
        if not refresh_token or not client_cfg:
            return str(token.get("access_token")) if token.get("access_token") else None

        token_uri = client_cfg.get("token_uri", "https://oauth2.googleapis.com/token")
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                token_uri,
                data={
                    "client_id": client_cfg["client_id"],
                    "client_secret": client_cfg.get("client_secret", ""),
                    "refresh_token": refresh_token,
                    "grant_type": "refresh_token",
                },
            )
            if resp.status_code != 200:
                return None
            refreshed = resp.json()
            token["access_token"] = refreshed["access_token"]
            token["expires_at"] = time.time() + int(refreshed.get("expires_in", 3600))
            self._write_token(token)
            return str(token["access_token"])

    async def connect_oauth(self) -> dict[str, Any]:
        client_cfg = self._read_client_config()
        if not client_cfg:
            return {
                "ok": False,
                "error": (
                    "Google OAuth credentials not found. Paste your Desktop OAuth credentials JSON "
                    "in Settings -> Google Workspace first."
                ),
            }

        state = secrets.token_urlsafe(16)
        code_verifier = secrets.token_urlsafe(64)
        code_challenge = (
            base64.urlsafe_b64encode(hashlib.sha256(code_verifier.encode("ascii")).digest())
            .rstrip(b"=")
            .decode("ascii")
        )

        auth_result: dict[str, str] = {}

        class CallbackHandler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):  # noqa: N802
                qs = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
                auth_result["code"] = (qs.get("code") or [""])[0]
                auth_result["state"] = (qs.get("state") or [""])[0]
                auth_result["error"] = (qs.get("error") or [""])[0]
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(
                    b"<html><body style='font-family:sans-serif;text-align:center;padding:40px'>"
                    b"<h2>Lael Connected!</h2><p>You can close this tab and return to Lael.</p></body></html>"
                )

            def log_message(self, format, *args):
                return

        def _wait_for_callback() -> tuple[int, dict[str, str]]:
            server = http.server.HTTPServer(("127.0.0.1", 0), CallbackHandler)
            server.timeout = 180
            port = server.server_address[1]
            redirect_uri = f"http://127.0.0.1:{port}"
            auth_uri = client_cfg.get("auth_uri", "https://accounts.google.com/o/oauth2/auth")
            params = urllib.parse.urlencode(
                {
                    "client_id": client_cfg["client_id"],
                    "redirect_uri": redirect_uri,
                    "response_type": "code",
                    "scope": " ".join(SCOPES),
                    "access_type": "offline",
                    "prompt": "consent",
                    "state": state,
                    "code_challenge": code_challenge,
                    "code_challenge_method": "S256",
                }
            )
            webbrowser.open(f"{auth_uri}?{params}")
            server.handle_request()
            server.server_close()
            return port, auth_result

        port, cb = await asyncio.to_thread(_wait_for_callback)
        if cb.get("error"):
            return {"ok": False, "error": f"Google OAuth error: {cb['error']}"}
        if not cb.get("code") or cb.get("state") != state:
            return {"ok": False, "error": "OAuth sign-in was cancelled or timed out."}

        token_uri = client_cfg.get("token_uri", "https://oauth2.googleapis.com/token")
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                token_uri,
                data={
                    "client_id": client_cfg["client_id"],
                    "client_secret": client_cfg.get("client_secret", ""),
                    "code": cb["code"],
                    "code_verifier": code_verifier,
                    "grant_type": "authorization_code",
                    "redirect_uri": f"http://127.0.0.1:{port}",
                },
            )
            if resp.status_code != 200:
                return {"ok": False, "error": f"Token exchange failed: {resp.text[:300]}"}
            tok = resp.json()

        tok["expires_at"] = time.time() + int(tok.get("expires_in", 3600))
        self._write_token(tok)
        return {"ok": True, "connected": True}

    def disconnect(self) -> dict[str, Any]:
        _, token_path = self._paths()
        if token_path.exists():
            token_path.unlink()
        return {"ok": True, "connected": False}

    async def list_upcoming_events(self, max_results: int = 8) -> dict[str, Any]:
        token = await self._get_valid_token()
        if not token:
            return {"ok": False, "error": "Google Workspace is not connected yet. Connect in Settings -> Google."}
        try:
            now = datetime.now(timezone.utc).isoformat()
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(
                    "https://www.googleapis.com/calendar/v3/calendars/primary/events",
                    headers={"Authorization": f"Bearer {token}"},
                    params={
                        "timeMin": now,
                        "maxResults": max_results,
                        "singleEvents": "true",
                        "orderBy": "startTime",
                    },
                )
                resp.raise_for_status()
                res = resp.json()
            items = []
            for ev in res.get("items", []):
                start = ev.get("start", {}).get("dateTime") or ev.get("start", {}).get("date", "")
                end = ev.get("end", {}).get("dateTime") or ev.get("end", {}).get("date", "")
                items.append(
                    {
                        "id": ev.get("id"),
                        "summary": ev.get("summary", "(No title)"),
                        "start": start,
                        "end": end,
                        "location": ev.get("location", ""),
                    }
                )
            return {"ok": True, "count": len(items), "events": items}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    async def create_calendar_event(
        self, summary: str, start_iso: str, end_iso: str, description: str = "", location: str = ""
    ) -> dict[str, Any]:
        token = await self._get_valid_token()
        if not token:
            return {"ok": False, "error": "Google Workspace is not connected yet."}
        try:
            body = {
                "summary": summary,
                "description": description,
                "location": location,
                "start": {"dateTime": start_iso},
                "end": {"dateTime": end_iso},
            }
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(
                    "https://www.googleapis.com/calendar/v3/calendars/primary/events",
                    headers={"Authorization": f"Bearer {token}"},
                    json=body,
                )
                resp.raise_for_status()
                created = resp.json()
            return {"ok": True, "id": created.get("id"), "htmlLink": created.get("htmlLink")}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    async def list_recent_emails(self, max_results: int = 6, query: str = "") -> dict[str, Any]:
        token = await self._get_valid_token()
        if not token:
            return {"ok": False, "error": "Google Workspace is not connected yet. Connect in Settings -> Google."}
        try:
            headers = {"Authorization": f"Bearer {token}"}
            params: dict[str, Any] = {"maxResults": max_results}
            if query:
                params["q"] = query
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(
                    "https://gmail.googleapis.com/gmail/v1/users/me/messages",
                    headers=headers,
                    params=params,
                )
                resp.raise_for_status()
                res = resp.json()
                emails = []
                for m in res.get("messages", []):
                    dresp = await client.get(
                        f"https://gmail.googleapis.com/gmail/v1/users/me/messages/{m['id']}",
                        headers=headers,
                        params={"format": "metadata", "metadataHeaders": ["From", "Subject", "Date"]},
                    )
                    if dresp.status_code != 200:
                        continue
                    detail = dresp.json()
                    hdrs = {h["name"]: h["value"] for h in detail.get("payload", {}).get("headers", [])}
                    emails.append(
                        {
                            "id": m["id"],
                            "from": hdrs.get("From", ""),
                            "subject": hdrs.get("Subject", "(No subject)"),
                            "date": hdrs.get("Date", ""),
                            "snippet": detail.get("snippet", ""),
                        }
                    )
            return {"ok": True, "count": len(emails), "emails": emails}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    async def send_email(self, to: str, subject: str, body: str) -> dict[str, Any]:
        token = await self._get_valid_token()
        if not token:
            return {"ok": False, "error": "Google Workspace is not connected yet."}
        try:
            msg = EmailMessage()
            msg.set_content(body)
            msg["To"] = to
            msg["Subject"] = subject
            raw = base64.urlsafe_b64encode(msg.as_bytes()).decode("utf-8")
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(
                    "https://gmail.googleapis.com/gmail/v1/users/me/messages/send",
                    headers={"Authorization": f"Bearer {token}"},
                    json={"raw": raw},
                )
                resp.raise_for_status()
                sent = resp.json()
            return {"ok": True, "id": sent.get("id")}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}


google_connector = GoogleConnector()


def register_google_tools() -> None:
    tool_registry.register(
        ToolDef(
            name="google_list_upcoming_events",
            description="List upcoming events from the user's Google Calendar.",
            parameters={
                "type": "object",
                "properties": {"max_results": {"type": "integer", "description": "Max events (default 8)"}},
            },
            category="google_workspace",
            tier=1,
            handler=lambda args: google_connector.list_upcoming_events(int(args.get("max_results", 8))),
        )
    )
    tool_registry.register(
        ToolDef(
            name="google_create_calendar_event",
            description="Create a new Google Calendar event (requires explicit user approval).",
            parameters={
                "type": "object",
                "properties": {
                    "summary": {"type": "string"},
                    "start_iso": {"type": "string", "description": "RFC3339 datetime e.g. 2026-11-25T10:00:00+03:00"},
                    "end_iso": {"type": "string", "description": "RFC3339 datetime e.g. 2026-11-25T11:00:00+03:00"},
                    "description": {"type": "string"},
                    "location": {"type": "string"},
                },
                "required": ["summary", "start_iso", "end_iso"],
            },
            category="google_workspace",
            tier=3,
            handler=lambda args: google_connector.create_calendar_event(
                summary=args.get("summary", ""),
                start_iso=args.get("start_iso", ""),
                end_iso=args.get("end_iso", ""),
                description=args.get("description", ""),
                location=args.get("location", ""),
            ),
        )
    )
    tool_registry.register(
        ToolDef(
            name="google_list_recent_emails",
            description="Search or list recent emails from the user's Gmail inbox.",
            parameters={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Optional Gmail search filter e.g. 'is:unread'"},
                    "max_results": {"type": "integer", "description": "Max emails (default 6)"},
                },
            },
            category="google_workspace",
            tier=1,
            handler=lambda args: google_connector.list_recent_emails(
                max_results=int(args.get("max_results", 6)), query=args.get("query", "")
            ),
        )
    )
    tool_registry.register(
        ToolDef(
            name="google_send_email",
            description="Send an email through Gmail (requires explicit user approval).",
            parameters={
                "type": "object",
                "properties": {
                    "to": {"type": "string"},
                    "subject": {"type": "string"},
                    "body": {"type": "string"},
                },
                "required": ["to", "subject", "body"],
            },
            category="google_workspace",
            tier=3,
            handler=lambda args: google_connector.send_email(
                to=args.get("to", ""), subject=args.get("subject", ""), body=args.get("body", "")
            ),
        )
    )
