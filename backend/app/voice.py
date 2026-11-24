from __future__ import annotations

import asyncio
import json
import tempfile
from pathlib import Path


async def list_windows_sapi_voices() -> list[str]:
    ps = r"""
    Add-Type -AssemblyName System.Speech
    $s = New-Object System.Speech.Synthesis.SpeechSynthesizer
    $s.GetInstalledVoices() | ForEach-Object { $_.VoiceInfo.Name } | ConvertTo-Json -Compress
    """
    proc = await asyncio.create_subprocess_exec(
        "powershell",
        "-NoProfile",
        "-NonInteractive",
        "-Command",
        ps,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    out, _ = await proc.communicate()
    raw = out.decode("utf-8", errors="ignore").strip()
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
        return [parsed] if isinstance(parsed, str) else list(parsed)
    except Exception:
        return []


async def synthesize_windows_sapi_wav(text: str, voice_name: str = "", rate: int = 0) -> bytes:
    """Synthesize offline speech on Windows using built-in System.Speech SAPI."""
    clean = text.replace("\r", " ").replace("\n", " ").strip()[:1800]
    if not clean:
        return b""

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        wav_path = Path(tmp.name)

    try:
        escaped_text = clean.replace("'", "''")
        escaped_voice = voice_name.replace("'", "''")
        escaped_path = str(wav_path).replace("'", "''")
        voice_cmd = f"try {{ $s.SelectVoice('{escaped_voice}') }} catch {{}}" if escaped_voice else ""
        ps = f"""
        Add-Type -AssemblyName System.Speech
        $s = New-Object System.Speech.Synthesis.SpeechSynthesizer
        {voice_cmd}
        $s.Rate = {max(-5, min(5, int(rate)))}
        $s.SetOutputToWaveFile('{escaped_path}')
        $s.Speak('{escaped_text}')
        $s.Dispose()
        """
        proc = await asyncio.create_subprocess_exec(
            "powershell",
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            ps,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await asyncio.wait_for(proc.communicate(), timeout=25)
        if wav_path.exists():
            return wav_path.read_bytes()
        return b""
    finally:
        try:
            wav_path.unlink(missing_ok=True)
        except Exception:
            pass
