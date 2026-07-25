"""NVIDIA NIM streaming client for Andre.

Targets the OpenAI-compatible chat-completions endpoint at
``https://integrate.api.nvidia.com/v1`` and the ``moonshotai/kimi-k2.6``
model. Kimi's thinking output arrives as ``reasoning_content`` inside
each streaming delta (separate from ``content``), so this client emits
those as distinct ``thinking`` and ``text`` events.

Tool calls follow OpenAI's streaming convention: each chunk contains a
partial ``tool_calls`` array indexed by tool-call position, with the
function ``name`` arriving first and ``arguments`` streamed in pieces.
This module accumulates those fragments and yields a single
``tool_call`` event when ``finish_reason == "tool_calls"``.
"""
from __future__ import annotations

import asyncio
import json
import os
from typing import Any, AsyncGenerator

import httpx


WEB_SEARCH_TOOL: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "web_search",
        "description": (
            "Search the web for current information. Use for App Store data, "
            "Reddit threads, market research, competitor analysis, and any "
            "real-world data needed."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query. Be specific. Max 10 words.",
                },
                "max_results": {
                    "type": "integer",
                    "description": "Number of results to return. Default 5, max 10.",
                    "default": 5,
                },
            },
            "required": ["query"],
        },
    },
}


class NIMClient:
    """Async streaming client for NVIDIA NIM chat completions."""

    def __init__(self, config: dict):
        self.model: str = config["model"]
        self.base_url: str = config["base_url"].rstrip("/")
        self.max_tokens: int = int(config.get("max_tokens", 16384))
        self.temperature: float = float(config.get("temperature", 1.0))
        self.top_p: float = float(config.get("top_p", 1.0))
        self.thinking: bool = bool(config.get("thinking", True))
        # Use NVIDIA's documented defaults (0/0) for Kimi K2.6 thinking
        # mode. We tried 0.3/0.1 in v2.3 to suppress character collapse,
        # but it pushed the model into low-probability token space and
        # caused semantic collapse instead. Repetition is now caught at
        # runtime by detect_collapse, so the sampler can stay vanilla.
        self.frequency_penalty: float = float(config.get("frequency_penalty", 0.0))
        self.presence_penalty: float = float(config.get("presence_penalty", 0.0))

        self.api_key = os.getenv("NVIDIA_API_KEY", "").strip()
        if not self.api_key:
            raise RuntimeError(
                "NVIDIA_API_KEY is not set. Add it to your .env file."
            )

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "text/event-stream",
            "Content-Type": "application/json",
        }

    def _payload(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "top_p": self.top_p,
            "frequency_penalty": self.frequency_penalty,
            "presence_penalty": self.presence_penalty,
            "stream": True,
            "chat_template_kwargs": {"thinking": self.thinking},
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"
        return payload

    async def stream_completion(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
    ) -> AsyncGenerator[dict[str, Any], None]:
        """Stream one chat-completion turn.

        Yields events:
          {"type":"thinking","content":str}
          {"type":"text","content":str}
          {"type":"tool_call","id":str,"name":str,"arguments":dict}
          {"type":"usage","input_tokens":int,"output_tokens":int}
          {"type":"finish","reason":str}
          {"type":"error","content":str}
        """
        url = f"{self.base_url}/chat/completions"
        payload = self._payload(messages, tools)

        attempts = 0
        while True:
            attempts += 1
            try:
                async for evt in self._do_stream(url, payload):
                    yield evt
                return
            except _RetryableError as exc:
                if attempts >= 3:
                    yield {
                        "type": "error",
                        "content": f"NIM stream failed after {attempts} retries: {exc}",
                    }
                    return
                backoff = 1.5 ** attempts
                await asyncio.sleep(backoff)
            except Exception as exc:
                yield {"type": "error", "content": f"NIM stream error: {exc}"}
                return

    async def _do_stream(
        self,
        url: str,
        payload: dict[str, Any],
    ) -> AsyncGenerator[dict[str, Any], None]:
        # Accumulators for streamed tool calls (OpenAI delta protocol)
        tool_call_buf: dict[int, dict[str, Any]] = {}
        finish_reason: str | None = None
        # Sliding window of recent streamed characters (text + thinking).
        # Used to detect repetition-collapse in real time and abort early.
        collapse_window = ""
        last_collapse_check = 0
        collapse_reason: str | None = None
        from utils.quality import detect_collapse, strip_control_tokens

        timeout = httpx.Timeout(connect=10.0, read=600.0, write=30.0, pool=10.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            try:
                async with client.stream(
                    "POST", url, headers=self._headers(), json=payload
                ) as resp:
                    if resp.status_code == 429 or 500 <= resp.status_code < 600:
                        body = await resp.aread()
                        raise _RetryableError(
                            f"HTTP {resp.status_code}: {body.decode('utf-8', 'ignore')[:300]}"
                        )
                    if resp.status_code >= 400:
                        body = await resp.aread()
                        yield {
                            "type": "error",
                            "content": (
                                f"NIM HTTP {resp.status_code}: "
                                f"{body.decode('utf-8', 'ignore')[:500]}"
                            ),
                        }
                        return

                    async for raw_line in resp.aiter_lines():
                        if not raw_line:
                            continue
                        line = raw_line.strip()
                        if not line.startswith("data:"):
                            continue
                        data = line[5:].strip()
                        if not data:
                            continue
                        if data == "[DONE]":
                            break

                        try:
                            chunk = json.loads(data)
                        except json.JSONDecodeError:
                            continue

                        # usage block (final chunk may carry it)
                        usage = chunk.get("usage")
                        if usage:
                            ct_details = usage.get("completion_tokens_details") or {}
                            reasoning_tokens = int(
                                ct_details.get("reasoning_tokens", 0) or 0
                            )
                            yield {
                                "type": "usage",
                                "input_tokens": int(usage.get("prompt_tokens", 0) or 0),
                                "output_tokens": int(
                                    usage.get("completion_tokens", 0) or 0
                                ),
                                "reasoning_tokens": reasoning_tokens,
                            }

                        choices = chunk.get("choices") or []
                        if not choices:
                            continue
                        choice = choices[0]
                        delta = choice.get("delta") or {}

                        # thinking content (Kimi-specific field)
                        reasoning_chunks: list[str] = []
                        reasoning = delta.get("reasoning_content")
                        if isinstance(reasoning, str) and reasoning:
                            reasoning_chunks.append(reasoning)
                        elif isinstance(reasoning, list):
                            for part in reasoning:
                                if isinstance(part, dict):
                                    t = part.get("text") or part.get("content")
                                    if isinstance(t, str) and t:
                                        reasoning_chunks.append(t)
                                elif isinstance(part, str) and part:
                                    reasoning_chunks.append(part)
                        for t in reasoning_chunks:
                            yield {"type": "thinking", "content": t}
                            collapse_window = (collapse_window + t)[-500:]

                        # visible content
                        text_chunks: list[str] = []
                        content = delta.get("content")
                        if isinstance(content, str) and content:
                            text_chunks.append(content)
                        elif isinstance(content, list):
                            for part in content:
                                if isinstance(part, dict):
                                    t = part.get("text")
                                    if isinstance(t, str) and t:
                                        text_chunks.append(t)
                        for t in text_chunks:
                            # Strip any Kimi control tokens that leaked
                            # into visible text. Per-chunk filtering only
                            # catches tokens contained within one chunk —
                            # cross-chunk fragments are mopped up by the
                            # final pass in base_agent before saving.
                            t = strip_control_tokens(t)
                            if not t:
                                continue
                            yield {"type": "text", "content": t}
                            collapse_window = (collapse_window + t)[-500:]

                        # Periodic collapse check (cheap — only re-scans
                        # when window has grown by another 60 chars).
                        if (
                            len(collapse_window) >= 200
                            and len(collapse_window) - last_collapse_check >= 60
                        ):
                            why = detect_collapse(collapse_window)
                            if why:
                                collapse_reason = why
                                break
                            last_collapse_check = len(collapse_window)

                        # tool_calls delta accumulation
                        tcs = delta.get("tool_calls")
                        if isinstance(tcs, list):
                            for tc in tcs:
                                idx = int(tc.get("index", 0) or 0)
                                slot = tool_call_buf.setdefault(
                                    idx, {"id": "", "name": "", "arguments": ""}
                                )
                                if tc.get("id"):
                                    slot["id"] = tc["id"]
                                fn = tc.get("function") or {}
                                if fn.get("name"):
                                    slot["name"] = fn["name"]
                                if isinstance(fn.get("arguments"), str):
                                    slot["arguments"] += fn["arguments"]

                        fr = choice.get("finish_reason")
                        if fr:
                            finish_reason = fr

                # Report collapse early-stop (don't emit tool_calls if we
                # bailed out of a degenerate generation — they're untrusted).
                if collapse_reason:
                    yield {
                        "type": "error",
                        "content": (
                            f"Repetition collapse detected mid-stream "
                            f"({collapse_reason}). Aborted early; saving "
                            f"clean output so far."
                        ),
                    }
                    yield {"type": "finish", "reason": "collapse"}
                    return

                # Emit any accumulated tool calls
                if tool_call_buf:
                    for idx in sorted(tool_call_buf.keys()):
                        slot = tool_call_buf[idx]
                        args_obj: dict[str, Any] = {}
                        if slot["arguments"]:
                            try:
                                args_obj = json.loads(slot["arguments"])
                            except json.JSONDecodeError:
                                args_obj = {"_raw": slot["arguments"]}
                        yield {
                            "type": "tool_call",
                            "id": slot["id"] or f"call_{idx}",
                            "name": slot["name"],
                            "arguments": args_obj,
                        }

                if finish_reason:
                    yield {"type": "finish", "reason": finish_reason}
            except (httpx.ReadTimeout, httpx.ConnectTimeout, httpx.ConnectError) as exc:
                raise _RetryableError(str(exc)) from exc


class _RetryableError(Exception):
    pass
