from __future__ import annotations

import asyncio
import json
import os
import platform
import shutil
import subprocess
import webbrowser
from pathlib import Path
from typing import Any

from app.config import settings_manager
from app.tools.registry import ToolDef, tool_registry


async def _run_ps(script: str, timeout: int = 15) -> tuple[int, str, str]:
    proc = await asyncio.create_subprocess_exec(
        "powershell",
        "-NoProfile",
        "-NonInteractive",
        "-Command",
        script,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        proc.kill()
        return -1, "", f"Command timed out after {timeout}s."
    return proc.returncode or 0, stdout.decode("utf-8", errors="ignore").strip(), stderr.decode("utf-8", errors="ignore").strip()


async def get_system_info() -> dict[str, Any]:
    disk = shutil.disk_usage(Path.home().anchor or "C:\\")
    disk_total_gb = round(disk.total / (1024**3), 1)
    disk_used_gb = round(disk.used / (1024**3), 1)
    disk_pct = round((disk.used / disk.total) * 100, 1) if disk.total else 0

    ps_script = r"""
    $os = Get-CimInstance Win32_OperatingSystem
    $cpu = Get-CimInstance Win32_Processor | Measure-Object -Property LoadPercentage -Average
    $bat = Get-CimInstance Win32_Battery -ErrorAction SilentlyContinue | Select-Object -First 1
    $totalMemGB = [math]::Round($os.TotalVisibleMemorySize / 1MB, 1)
    $freeMemGB = [math]::Round($os.FreePhysicalMemory / 1MB, 1)
    $usedMemGB = [math]::Round($totalMemGB - $freeMemGB, 1)
    $memPct = if ($totalMemGB -gt 0) { [math]::Round(($usedMemGB / $totalMemGB) * 100, 1) } else { 0 }
    [PSCustomObject]@{
        cpu_percent = [math]::Round(($cpu.Average -as [double]), 1)
        memory_total_gb = $totalMemGB
        memory_used_gb = $usedMemGB
        memory_percent = $memPct
        battery_percent = if ($bat) { $bat.EstimatedChargeRemaining } else { $null }
        battery_charging = if ($bat) { $bat.BatteryStatus -eq 2 } else { $null }
        computer_name = $env:COMPUTERNAME
        user_name = $env:USERNAME
    } | ConvertTo-Json -Compress
    """
    code, out, _ = await _run_ps(ps_script, timeout=10)
    extra: dict[str, Any] = {}
    if code == 0 and out:
        try:
            extra = json.loads(out)
        except Exception:
            extra = {}

    return {
        "ok": True,
        "os": f"{platform.system()} {platform.release()}",
        "disk_total_gb": disk_total_gb,
        "disk_used_gb": disk_used_gb,
        "disk_percent": disk_pct,
        "cpu_percent": extra.get("cpu_percent"),
        "memory_total_gb": extra.get("memory_total_gb"),
        "memory_used_gb": extra.get("memory_used_gb"),
        "memory_percent": extra.get("memory_percent"),
        "battery_percent": extra.get("battery_percent"),
        "battery_charging": extra.get("battery_charging"),
        "computer_name": extra.get("computer_name", platform.node()),
        "user_name": extra.get("user_name", os.environ.get("USERNAME", "")),
    }


async def open_application(app_name: str) -> dict[str, Any]:
    auto_cfg = settings_manager.get().get("automation", {})
    if not auto_cfg.get("allow_app_launch", True):
        return {"ok": False, "error": "Application launching is disabled in Settings -> Automation."}
    allowed: dict[str, str] = auto_cfg.get("allowed_apps", {})
    key = app_name.strip().lower()
    target = allowed.get(key)
    if not target:
        return {
            "ok": False,
            "error": f"App '{app_name}' is not in your allowed apps list. Allowed: {', '.join(sorted(allowed.keys()))}. You can add custom apps in Settings.",
        }
    try:
        if target.endswith(":"):
            os.startfile(target)  # type: ignore[attr-defined]
        else:
            subprocess.Popen([target], shell=False)
        return {"ok": True, "launched": key, "target": target}
    except Exception as exc:
        return {"ok": False, "error": f"Failed to launch '{key}': {exc}"}


async def open_url_or_path(target: str) -> dict[str, Any]:
    val = target.strip()
    if not val:
        return {"ok": False, "error": "Target URL or path is required."}
    try:
        if val.startswith(("http://", "https://")):
            webbrowser.open(val)
            return {"ok": True, "opened": val, "type": "url"}
        p = Path(val).expanduser()
        if not p.exists():
            return {"ok": False, "error": f"Path does not exist: {val}"}
        os.startfile(str(p))  # type: ignore[attr-defined]
        return {"ok": True, "opened": str(p), "type": "path"}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


async def _get_clipboard(args: dict[str, Any]) -> dict[str, Any]:
    code, out, err = await _run_ps("Get-Clipboard -Raw", timeout=5)
    if code != 0:
        return {"ok": False, "error": err or "Could not read clipboard."}
    return {"ok": True, "text": out[:4000]}


async def _set_clipboard(args: dict[str, Any]) -> dict[str, Any]:
    text = args.get("text", "")
    escaped = text.replace("'", "''")
    code, _, err = await _run_ps(f"Set-Clipboard -Value '{escaped}'", timeout=5)
    if code != 0:
        return {"ok": False, "error": err or "Could not write clipboard."}
    return {"ok": True, "length": len(text)}


async def _run_powershell_tool(args: dict[str, Any]) -> dict[str, Any]:
    cmd = (args.get("command") or "").strip()
    if not cmd:
        return {"ok": False, "error": "Command is required."}
    code, out, err = await _run_ps(cmd, timeout=int(args.get("timeout", 25)))
    return {
        "ok": code == 0,
        "exit_code": code,
        "stdout": out[:6000],
        "stderr": err[:2000],
    }


def register_system_tools() -> None:
    tool_registry.register(
        ToolDef(
            name="get_system_info",
            description="Check Windows PC health: CPU load, RAM usage, disk space, and battery status.",
            parameters={"type": "object", "properties": {}},
            category="system_automation",
            tier=1,
            handler=lambda _args: get_system_info(),
        )
    )
    tool_registry.register(
        ToolDef(
            name="open_application",
            description="Launch an allowed Windows application by alias (e.g. notepad, calculator, explorer, edge, chrome, vscode, terminal, settings).",
            parameters={
                "type": "object",
                "properties": {"app_name": {"type": "string", "description": "App alias from Settings -> Automation"}},
                "required": ["app_name"],
            },
            category="system_automation",
            tier=2,
            handler=lambda args: open_application(args.get("app_name", "")),
        )
    )
    tool_registry.register(
        ToolDef(
            name="open_url_or_path",
            description="Open a web URL in the default browser or open a local Windows file/folder.",
            parameters={
                "type": "object",
                "properties": {"target": {"type": "string", "description": "HTTP/HTTPS URL or local path"}},
                "required": ["target"],
            },
            category="system_automation",
            tier=2,
            handler=lambda args: open_url_or_path(args.get("target", "")),
        )
    )
    tool_registry.register(
        ToolDef(
            name="get_clipboard",
            description="Read the current text contents of the Windows clipboard.",
            parameters={"type": "object", "properties": {}},
            category="system_automation",
            tier=1,
            handler=_get_clipboard,
        )
    )
    tool_registry.register(
        ToolDef(
            name="set_clipboard",
            description="Copy text to the Windows clipboard.",
            parameters={
                "type": "object",
                "properties": {"text": {"type": "string"}},
                "required": ["text"],
            },
            category="system_automation",
            tier=2,
            handler=_set_clipboard,
        )
    )
    tool_registry.register(
        ToolDef(
            name="run_powershell_command",
            description="Run a Windows PowerShell command. Always requires explicit user approval in the UI before executing.",
            parameters={
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "PowerShell command to execute"},
                    "timeout": {"type": "integer", "description": "Timeout in seconds (default 25)"},
                },
                "required": ["command"],
            },
            category="system_automation",
            tier=3,
            handler=_run_powershell_tool,
        )
    )
