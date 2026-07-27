import json as _json
from typing import Callable, Iterator
import httpx
from .base import Message, Tool, TextDelta, ToolCallEvent, Done, Event

_API = "https://api.anthropic.com/v1/messages"
_VERSION = "2023-06-01"

def _message_to_dict(m: Message) -> dict:
    if m.role == "tool":
        return {"role": "user",
                "content": [{"type": "tool_result", "tool_use_id": m.tool_call_id,
                             "content": m.content}]}
    if m.role == "assistant" and m.tool_calls:
        blocks: list[dict] = []
        if m.content:
            blocks.append({"type": "text", "text": m.content})
        for tc in m.tool_calls:
            blocks.append({"type": "tool_use", "id": tc.id, "name": tc.name,
                           "input": tc.arguments})
        return {"role": "assistant", "content": blocks}
    return {"role": m.role, "content": m.content}

def build_payload(messages: list[Message], tools: list[Tool], model: str,
                  system: str = "") -> dict:
    out: list[dict] = []
    pending: list[dict] = []

    def flush() -> None:
        nonlocal pending
        if pending:
            out.append({"role": "user", "content": pending})
            pending = []

    for m in messages:
        if m.role == "tool":
            pending.append({"type": "tool_result", "tool_use_id": m.tool_call_id,
                            "content": m.content})
        else:
            flush()
            out.append(_message_to_dict(m))
    flush()
    payload: dict = {
        "model": model,
        "stream": True,
        "max_tokens": 4096,
        "messages": out,
    }
    if system:
        payload["system"] = system
    if tools:
        payload["tools"] = [
            {"name": t.name, "description": t.description, "input_schema": t.parameters}
            for t in tools
        ]
    return payload

def parse_sse_event(event_type: str, data: dict) -> Event | None:
    # Text deltas only. Tool-call assembly and Done are handled in chat()
    # because they require state across multiple events.
    if event_type == "content_block_delta":
        delta = data.get("delta", {})
        if delta.get("type") == "text_delta":
            return TextDelta(delta.get("text", ""))
    return None

def _httpx_poster(url: str, headers: dict, json: dict) -> Iterator[tuple[str, dict]]:
    with httpx.stream("POST", url, headers=headers, json=json, timeout=None) as resp:
        resp.raise_for_status()
        event_type = ""
        for line in resp.iter_lines():
            if line.startswith("event:"):
                event_type = line[len("event:"):].strip()
            elif line.startswith("data:"):
                yield event_type, _json.loads(line[len("data:"):].strip())

class AnthropicProvider:
    def __init__(self, api_key: str | None, model: str, poster: Callable | None = None):
        self.api_key = api_key
        self.model = model
        self._poster = poster or _httpx_poster

    def chat(self, messages: list[Message], tools: list[Tool],
             system: str = "") -> Iterator[Event]:
        headers = {"Content-Type": "application/json",
                   "anthropic-version": _VERSION,
                   "x-api-key": self.api_key or ""}
        payload = build_payload(messages, tools, self.model, system)
        tool_buffer: dict[int, dict] = {}
        stop_reason = "end"
        for event_type, data in self._poster(_API, headers, payload):
            if event_type == "content_block_start":
                block = data.get("content_block", {})
                if block.get("type") == "tool_use":
                    idx = data.get("index", 0)
                    tool_buffer[idx] = {"id": block.get("id", ""),
                                        "name": block.get("name", ""), "arguments": ""}
            elif event_type == "content_block_delta":
                delta = data.get("delta", {})
                if delta.get("type") == "input_json_delta":
                    idx = data.get("index", 0)
                    if idx in tool_buffer:
                        tool_buffer[idx]["arguments"] += delta.get("partial_json", "")
                else:
                    ev = parse_sse_event(event_type, data)
                    if ev is not None:
                        yield ev
            elif event_type == "content_block_stop":
                idx = data.get("index", 0)
                buf = tool_buffer.pop(idx, None)
                if buf is not None:
                    try:
                        args = _json.loads(buf["arguments"] or "{}")
                    except _json.JSONDecodeError:
                        args = {}
                    yield ToolCallEvent(buf["id"], buf["name"], args)
            elif event_type == "message_delta":
                sr = (data.get("delta") or {}).get("stop_reason")
                if sr:
                    stop_reason = "tool_use" if sr == "tool_use" else "end"
            elif event_type == "message_stop":
                yield Done(stop_reason)
