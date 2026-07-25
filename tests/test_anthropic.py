from pentai.providers.base import Message, Tool, TextDelta, ToolCallEvent, Done
from pentai.providers.anthropic import build_payload, parse_sse_event, AnthropicProvider

def test_build_payload_shape():
    p = build_payload([Message("user", "hi")], [Tool("run_command", "run", {"type": "object"})],
                      "claude-opus-4")
    assert p["stream"] is True
    assert p["model"] == "claude-opus-4"
    assert p["tools"][0]["name"] == "run_command"
    assert "max_tokens" in p

def test_parse_text_delta():
    ev = parse_sse_event("content_block_delta",
                         {"delta": {"type": "text_delta", "text": "hi"}})
    assert isinstance(ev, TextDelta) and ev.text == "hi"

def test_chat_streams_text_and_done():
    events_in = [
        ("content_block_delta", {"delta": {"type": "text_delta", "text": "hi"}}),
        ("message_stop", {}),
    ]
    prov = AnthropicProvider("k", "claude-opus-4",
                             poster=lambda url, headers, json: iter(events_in))
    out = list(prov.chat([Message("user", "hi")], []))
    assert any(isinstance(e, TextDelta) and e.text == "hi" for e in out)
    assert any(isinstance(e, Done) and e.stop_reason == "end" for e in out)

def test_chat_assembles_streamed_tool_call():
    events_in = [
        ("content_block_start", {"index": 0,
            "content_block": {"type": "tool_use", "id": "tu_1", "name": "run_command", "input": {}}}),
        ("content_block_delta", {"index": 0,
            "delta": {"type": "input_json_delta", "partial_json": "{\"command\":"}}),
        ("content_block_delta", {"index": 0,
            "delta": {"type": "input_json_delta", "partial_json": " \"ls\"}"}}),
        ("content_block_stop", {"index": 0}),
        ("message_delta", {"delta": {"stop_reason": "tool_use"}}),
        ("message_stop", {}),
    ]
    prov = AnthropicProvider("k", "claude-opus-4",
                             poster=lambda url, headers, json: iter(events_in))
    out = list(prov.chat([Message("user", "scan")], []))
    tcs = [e for e in out if isinstance(e, ToolCallEvent)]
    assert len(tcs) == 1
    assert tcs[0].id == "tu_1"
    assert tcs[0].name == "run_command"
    assert tcs[0].arguments == {"command": "ls"}
    assert any(isinstance(e, Done) and e.stop_reason == "tool_use" for e in out)
