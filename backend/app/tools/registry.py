from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

from app.config import settings_manager
from app.database import db, utc_now

ToolHandler = Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]


@dataclass
class ToolDef:
    name: str
    description: str
    parameters: dict[str, Any]
    category: str  # tasks_notes_reminders | knowledge_base | web_search | daily_briefing | system_automation | google_workspace
    tier: int  # 1 = read-only, 2 = safe action, 3 = requires explicit approval
    handler: ToolHandler


@dataclass
class PendingApproval:
    id: str
    tool_name: str
    arguments: dict[str, Any]
    summary: str
    tier: int
    created_at: str = field(default_factory=utc_now)
    status: str = "pending"  # pending | approved | denied
    result: dict[str, Any] | None = None


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, ToolDef] = {}
        self._pending: dict[str, PendingApproval] = {}

    def register(self, tool: ToolDef) -> None:
        self._tools[tool.name] = tool

    def list_enabled_schemas(self) -> list[dict[str, Any]]:
        caps = settings_manager.get().get("capabilities", {})
        schemas: list[dict[str, Any]] = []
        for t in self._tools.values():
            if caps.get(t.category, True):
                schemas.append(
                    {
                        "name": t.name,
                        "description": t.description,
                        "parameters": t.parameters,
                    }
                )
        return schemas

    def list_all_metadata(self) -> list[dict[str, Any]]:
        caps = settings_manager.get().get("capabilities", {})
        return [
            {
                "name": t.name,
                "description": t.description,
                "category": t.category,
                "tier": t.tier,
                "enabled": bool(caps.get(t.category, True)),
            }
            for t in self._tools.values()
        ]

    def _needs_approval(self, tool: ToolDef) -> bool:
        if tool.tier < 3:
            return False
        if tool.name == "run_powershell_command":
            return bool(settings_manager.get().get("automation", {}).get("require_approval_for_shell", True))
        return True

    async def execute(
        self, name: str, arguments: dict[str, Any], bypass_approval: bool = False
    ) -> dict[str, Any]:
        tool = self._tools.get(name)
        if not tool:
            return {"ok": False, "error": f"Unknown tool: {name}"}

        caps = settings_manager.get().get("capabilities", {})
        if not caps.get(tool.category, True):
            return {"ok": False, "error": f"Capability '{tool.category}' is disabled in Settings."}

        if not bypass_approval and self._needs_approval(tool):
            pid = uuid.uuid4().hex[:10]
            summary = self._summarize_call(name, arguments)
            pending = PendingApproval(
                id=pid,
                tool_name=name,
                arguments=arguments,
                summary=summary,
                tier=tool.tier,
            )
            self._pending[pid] = pending
            db.log_audit(name, tool.tier, summary, arguments, "awaiting_approval")
            return {
                "ok": False,
                "status": "approval_required",
                "approval_id": pid,
                "summary": summary,
                "message": (
                    f"Action '{summary}' requires explicit user approval (Tier 3). "
                    "An approval request has been queued in the Lael desktop UI. "
                    "Inform the user to click Approve or Deny."
                ),
            }

        try:
            res = await tool.handler(arguments or {})
            db.log_audit(
                name,
                tool.tier,
                self._summarize_call(name, arguments),
                {"arguments": arguments, "ok": res.get("ok", True)},
                "executed",
            )
            return res
        except Exception as exc:
            db.log_audit(name, tool.tier, f"Failed: {name}", {"error": str(exc)}, "error")
            return {"ok": False, "error": str(exc)}

    def list_pending_approvals(self) -> list[dict[str, Any]]:
        return [
            {
                "id": p.id,
                "tool_name": p.tool_name,
                "arguments": p.arguments,
                "summary": p.summary,
                "tier": p.tier,
                "created_at": p.created_at,
                "status": p.status,
                "result": p.result,
            }
            for p in self._pending.values()
            if p.status == "pending"
        ]

    async def resolve_approval(self, approval_id: str, approved: bool) -> dict[str, Any]:
        pending = self._pending.get(approval_id)
        if not pending:
            return {"ok": False, "error": "Approval request not found."}
        if pending.status != "pending":
            return {"ok": False, "error": f"Request already {pending.status}."}

        if not approved:
            pending.status = "denied"
            db.log_audit(pending.tool_name, pending.tier, pending.summary, pending.arguments, "denied")
            return {"ok": True, "status": "denied", "approval_id": approval_id}

        pending.status = "approved"
        result = await self.execute(pending.tool_name, pending.arguments, bypass_approval=True)
        pending.result = result
        return {"ok": True, "status": "approved", "approval_id": approval_id, "result": result}

    @staticmethod
    def _summarize_call(name: str, arguments: dict[str, Any]) -> str:
        if name == "run_powershell_command":
            return f"Run PowerShell: {arguments.get('command', '')}"
        if name == "google_send_email":
            return f"Send email to {arguments.get('to', '')} — '{arguments.get('subject', '')}'"
        if name == "google_create_calendar_event":
            return f"Create calendar event '{arguments.get('summary', '')}' at {arguments.get('start_iso', '')}"
        return f"{name}({', '.join(f'{k}={v!r}' for k, v in list(arguments.items())[:3])})"


tool_registry = ToolRegistry()
