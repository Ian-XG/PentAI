import json as _json
from typing import Callable, Iterator
import httpx
from .base import Message, Tool, TextDelta, ToolCallEvent, Done, Notice, Event

_NO_TOOLS_NOTICE = (
    "this model doesn't support tool-calling, so PentAI can't run commands with "
    "it - it will chat only. Switch to a tool-capable model with /setup or "
    "`pentai --settings` (e.g. gpt-oss:20b, Claude, or GPT-4o) for the full agent.")

def _message_to_dict(m: Message) -> dict:
    if m.role == "tool":
        return {"role": "tool", "tool_call_id": m.tool_call_id, "content": m.content}
    d: dict = {"role": m.role, "content": m.content}
    if m.tool_calls:
        d["tool_calls"] = [
            {"id": tc.id, "type": "function",
             "function": {"name": tc.name, "arguments": _json.dumps(tc.arguments)}}
            for tc in m.tool_calls
        ]
    return d

def build_payload(messages: list[Message], tools: list[Tool], model: str,
                  system: str = "") -> dict:
    msgs: list[dict] = [{"role": "system", "content": system}] if system else []
    msgs.extend(_message_to_dict(m) for m in messages)
    payload: dict = {
        "model": model,
        "stream": True,
        "messages": msgs,
    }
    if tools:
        payload["tools"] = [
            {"type": "function",
             "function": {"name": t.name, "description": t.description,
                          "parameters": t.parameters}}
            for t in tools
        ]
    return payload

def parse_sse_chunk(data: dict) -> Event | None:
    choice = (data.get("choices") or [{}])[0]
    delta = choice.get("delta", {})
    if delta.get("content"):
        return TextDelta(delta["content"])
    if choice.get("finish_reason"):
        reason = "tool_use" if choice["finish_reason"] == "tool_calls" else "end"
        return Done(reason)
    return None

def _httpx_poster(url: str, headers: dict, json: dict) -> Iterator[str]:
    with httpx.stream("POST", url, headers=headers, json=json, timeout=None) as resp:
        resp.raise_for_status()
        for line in resp.iter_lines():
            yield line

class OpenAICompatProvider:
    def __init__(self, base_url: str, api_key: str | None, model: str,
                 poster: Callable | None = None):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self._poster = poster or _httpx_poster
        self._tools_unsupported = False

    def chat(self, messages: list[Message], tools: list[Tool],
             system: str = "") -> Iterator[Event]:
        payload = build_payload(messages, tools, self.model, system)
        # Once we've learned this model rejects tools, don't send them again
        # (avoids a wasted 400 round-trip every turn).
        if self._tools_unsupported:
            payload.pop("tools", None)
        emitted = False
        try:
            for ev in self._stream(payload):
                emitted = True
                yield ev
        except httpx.HTTPStatusError as e:
            # Many local models (e.g. llama2-uncensored via Ollama) don't support
            # the OpenAI `tools` param and reject it with 400. If nothing streamed
            # yet, retry as a plain chat so any local model still works.
            if e.response.status_code == 400 and payload.get("tools") and not emitted:
                self._tools_unsupported = True
                yield Notice(_NO_TOOLS_NOTICE)
                payload.pop("tools", None)
                yield from self._stream(payload)
            else:
                raise

    def _stream(self, payload: dict) -> Iterator[Event]:
        url = f"{self.base_url}/chat/completions"
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        tool_buffer: dict[int, dict] = {}
        for line in self._poster(url, headers, payload):
            if not line or not line.startswith("data:"):
                continue
            data_str = line[len("data:"):].strip()
            if data_str == "[DONE]":
                break
            data = _json.loads(data_str)
            choice = (data.get("choices") or [{}])[0]
            delta = choice.get("delta", {})
            for tc in delta.get("tool_calls") or []:
                idx = tc.get("index", 0)
                buf = tool_buffer.setdefault(idx, {"id": "", "name": "", "arguments": ""})
                if tc.get("id"):
                    buf["id"] = tc["id"]
                fn = tc.get("function") or {}
                if fn.get("name"):
                    buf["name"] = fn["name"]
                if fn.get("arguments"):
                    buf["arguments"] += fn["arguments"]
            finish = choice.get("finish_reason")
            if finish == "tool_calls":
                for i in sorted(tool_buffer):
                    buf = tool_buffer[i]
                    try:
                        args = _json.loads(buf["arguments"] or "{}")
                    except _json.JSONDecodeError:
                        args = {}
                    yield ToolCallEvent(buf["id"], buf["name"], args)
                tool_buffer = {}
                yield Done("tool_use")
            elif finish:
                yield Done("end")
            else:
                ev = parse_sse_chunk(data)
                if ev is not None:
                    yield ev
