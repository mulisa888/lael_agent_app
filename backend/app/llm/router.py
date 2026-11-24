from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from typing import Any

import httpx


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class LLMResponse:
    content: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    provider: str = ""
    model: str = ""
    error: str | None = None


class LLMRouter:
    """Switchable LLM client supporting Ollama (local), Gemini API, and OpenAI-compatible APIs."""

    async def list_ollama_models(self, base_url: str) -> dict[str, Any]:
        url = base_url.rstrip("/") + "/api/tags"
        try:
            async with httpx.AsyncClient(timeout=4.0) as client:
                resp = await client.get(url)
                resp.raise_for_status()
                data = resp.json()
                models = [m.get("name", "") for m in data.get("models", []) if m.get("name")]
                return {"online": True, "models": models}
        except Exception as exc:
            return {"online": False, "models": [], "error": str(exc)}

    async def chat(
        self,
        ai_cfg: dict[str, Any],
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> LLMResponse:
        provider = ai_cfg.get("provider", "ollama")
        if provider == "gemini":
            return await self._chat_gemini(ai_cfg, messages, tools)
        if provider == "openai_compat":
            return await self._chat_openai(ai_cfg, messages, tools)
        return await self._chat_ollama(ai_cfg, messages, tools)

    async def _chat_ollama(
        self,
        ai_cfg: dict[str, Any],
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> LLMResponse:
        base_url = ai_cfg.get("ollama_base_url", "http://127.0.0.1:11434").rstrip("/")
        model = ai_cfg.get("ollama_model", "llama3.2")
        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": False,
            "options": {"temperature": float(ai_cfg.get("temperature", 0.7))},
        }
        if tools:
            payload["tools"] = [
                {
                    "type": "function",
                    "function": {
                        "name": t["name"],
                        "description": t["description"],
                        "parameters": t["parameters"],
                    },
                }
                for t in tools
            ]

        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                resp = await client.post(f"{base_url}/api/chat", json=payload)
                # Some Ollama models don't support native tools; retry without tools if 400 mentions tools
                if resp.status_code == 400 and "tools" in resp.text.lower() and "tools" in payload:
                    payload.pop("tools", None)
                    resp = await client.post(f"{base_url}/api/chat", json=payload)
                resp.raise_for_status()
                data = resp.json()
        except httpx.ConnectError:
            return LLMResponse(
                provider="ollama",
                model=model,
                error=(
                    f"Could not connect to Ollama at {base_url}. "
                    "Start Ollama (or switch to Gemini API in Settings)."
                ),
            )
        except Exception as exc:
            return LLMResponse(provider="ollama", model=model, error=f"Ollama error: {exc}")

        msg = data.get("message", {})
        parsed_calls: list[ToolCall] = []
        for idx, tc in enumerate(msg.get("tool_calls") or []):
            fn = tc.get("function", {})
            args = fn.get("arguments", {})
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except Exception:
                    args = {}
            parsed_calls.append(
                ToolCall(
                    id=tc.get("id") or f"ollama_tc_{idx}_{uuid.uuid4().hex[:6]}",
                    name=fn.get("name", ""),
                    arguments=args if isinstance(args, dict) else {},
                )
            )
        return LLMResponse(
            content=msg.get("content", "") or "",
            tool_calls=parsed_calls,
            provider="ollama",
            model=model,
        )

    async def _chat_gemini(
        self,
        ai_cfg: dict[str, Any],
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> LLMResponse:
        api_key = (ai_cfg.get("gemini_api_key") or "").strip()
        model = ai_cfg.get("gemini_model", "gemini-2.5-flash").strip()
        if not api_key:
            return LLMResponse(
                provider="gemini",
                model=model,
                error="Gemini API key is missing. Add your key in Settings -> AI Engine (or switch to local Ollama).",
            )

        system_texts: list[str] = []
        contents: list[dict[str, Any]] = []
        for m in messages:
            role = m.get("role")
            if role == "system":
                system_texts.append(m.get("content", ""))
            elif role == "user":
                contents.append({"role": "user", "parts": [{"text": m.get("content", "")}]})
            elif role == "assistant":
                parts: list[dict[str, Any]] = []
                if m.get("content"):
                    parts.append({"text": m["content"]})
                for tc in m.get("tool_calls") or []:
                    fn = tc.get("function", {})
                    args = fn.get("arguments", {})
                    if isinstance(args, str):
                        try:
                            args = json.loads(args)
                        except Exception:
                            args = {}
                    parts.append({"functionCall": {"name": fn.get("name", ""), "args": args}})
                if parts:
                    contents.append({"role": "model", "parts": parts})
            elif role == "tool":
                tool_name = m.get("name", "tool")
                raw_content = m.get("content", "")
                try:
                    parsed = json.loads(raw_content)
                    if not isinstance(parsed, dict):
                        parsed = {"result": parsed}
                except Exception:
                    parsed = {"result": raw_content}
                contents.append(
                    {
                        "role": "user",
                        "parts": [
                            {
                                "functionResponse": {
                                    "name": tool_name,
                                    "response": parsed,
                                }
                            }
                        ],
                    }
                )

        payload: dict[str, Any] = {
            "contents": contents,
            "generationConfig": {"temperature": float(ai_cfg.get("temperature", 0.7))},
        }
        if system_texts:
            payload["systemInstruction"] = {"parts": [{"text": "\n\n".join(system_texts)}]}
        if tools:
            payload["tools"] = [
                {
                    "functionDeclarations": [
                        {
                            "name": t["name"],
                            "description": t["description"],
                            "parameters": t["parameters"],
                        }
                        for t in tools
                    ]
                }
            ]

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        try:
            async with httpx.AsyncClient(timeout=90.0) as client:
                resp = await client.post(url, params={"key": api_key}, json=payload)
                if resp.status_code >= 400:
                    return LLMResponse(
                        provider="gemini",
                        model=model,
                        error=f"Gemini API error ({resp.status_code}): {resp.text[:350]}",
                    )
                data = resp.json()
        except Exception as exc:
            return LLMResponse(provider="gemini", model=model, error=f"Gemini connection error: {exc}")

        candidates = data.get("candidates") or []
        if not candidates:
            return LLMResponse(provider="gemini", model=model, error="Gemini returned no candidates.")

        parts = candidates[0].get("content", {}).get("parts", [])
        text_chunks: list[str] = []
        calls: list[ToolCall] = []
        for idx, part in enumerate(parts):
            if "text" in part:
                text_chunks.append(part["text"])
            if "functionCall" in part:
                fc = part["functionCall"]
                calls.append(
                    ToolCall(
                        id=f"gemini_tc_{idx}_{uuid.uuid4().hex[:6]}",
                        name=fc.get("name", ""),
                        arguments=fc.get("args", {}) or {},
                    )
                )
        return LLMResponse(
            content="".join(text_chunks).strip(),
            tool_calls=calls,
            provider="gemini",
            model=model,
        )

    async def _chat_openai(
        self,
        ai_cfg: dict[str, Any],
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> LLMResponse:
        base_url = ai_cfg.get("openai_base_url", "https://api.openai.com/v1").rstrip("/")
        api_key = (ai_cfg.get("openai_api_key") or "").strip()
        model = ai_cfg.get("openai_model", "gpt-4o-mini").strip()
        if not api_key:
            return LLMResponse(
                provider="openai_compat",
                model=model,
                error="OpenAI-compatible API key is missing. Add it in Settings -> AI Engine.",
            )

        formatted_msgs = []
        for m in messages:
            item: dict[str, Any] = {"role": m["role"], "content": m.get("content", "")}
            if m.get("tool_calls"):
                item["tool_calls"] = [
                    {
                        "id": tc.get("id", f"call_{i}"),
                        "type": "function",
                        "function": {
                            "name": tc["function"]["name"],
                            "arguments": (
                                json.dumps(tc["function"]["arguments"])
                                if isinstance(tc["function"]["arguments"], dict)
                                else str(tc["function"]["arguments"])
                            ),
                        },
                    }
                    for i, tc in enumerate(m["tool_calls"])
                ]
            if m["role"] == "tool":
                item["tool_call_id"] = m.get("tool_call_id", "call_0")
            formatted_msgs.append(item)

        payload: dict[str, Any] = {
            "model": model,
            "messages": formatted_msgs,
            "temperature": float(ai_cfg.get("temperature", 0.7)),
        }
        if tools:
            payload["tools"] = [
                {
                    "type": "function",
                    "function": {
                        "name": t["name"],
                        "description": t["description"],
                        "parameters": t["parameters"],
                    },
                }
                for t in tools
            ]

        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        try:
            async with httpx.AsyncClient(timeout=90.0) as client:
                resp = await client.post(f"{base_url}/chat/completions", headers=headers, json=payload)
                if resp.status_code >= 400:
                    return LLMResponse(
                        provider="openai_compat",
                        model=model,
                        error=f"API error ({resp.status_code}): {resp.text[:350]}",
                    )
                data = resp.json()
        except Exception as exc:
            return LLMResponse(provider="openai_compat", model=model, error=f"API connection error: {exc}")

        choice = (data.get("choices") or [{}])[0].get("message", {})
        calls: list[ToolCall] = []
        for idx, tc in enumerate(choice.get("tool_calls") or []):
            fn = tc.get("function", {})
            raw_args = fn.get("arguments", "{}")
            try:
                args = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
            except Exception:
                args = {}
            calls.append(
                ToolCall(
                    id=tc.get("id") or f"oai_tc_{idx}",
                    name=fn.get("name", ""),
                    arguments=args if isinstance(args, dict) else {},
                )
            )
        return LLMResponse(
            content=choice.get("content") or "",
            tool_calls=calls,
            provider="openai_compat",
            model=model,
        )


llm_router = LLMRouter()
