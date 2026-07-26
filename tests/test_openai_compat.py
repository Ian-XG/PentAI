from pentai.providers.base import Message, Tool, TextDelta, ToolCallEvent, Done
from pentai.providers.openai_compat import build_payload, parse_sse_chunk, OpenAICompatProvider

def test_build_payload_includes_stream_and_tools():
    tools = [Tool("run_command", "run", {"type": "object"})]
    p = build_payload([Message("user", "hi")], tools, "gpt-4o")
    assert p["stream"] is True
    assert p["model"] == "gpt-4o"
    assert p["tools"][0]["function"]["name"] == "run_command"
    assert p["messages"][0] == {"role": "user", "content": "hi"}

def test_build_payload_prepends_system():
    p = build_payload([Message("user", "hi")], [], "gpt-4o", system="be ethical")
    assert p["messages"][0] == {"role": "system", "content": "be ethical"}
    p2 = build_payload([Message("user", "hi")], [], "gpt-4o")
    assert p2["messages"][0]["role"] == "user"

def test_parse_text_delta():
    chunk = {"choices": [{"delta": {"content": "he"}}]}
    ev = parse_sse_chunk(chunk)
    assert isinstance(ev, TextDelta) and ev.text == "he"

def test_parse_done():
    chunk = {"choices": [{"delta": {}, "finish_reason": "stop"}]}
    ev = parse_sse_chunk(chunk)
    assert isinstance(ev, Done) and ev.stop_reason == "end"

def test_chat_streams_from_injected_poster():
    lines = [
        'data: {"choices":[{"delta":{"content":"hi"}}]}',
        'data: {"choices":[{"delta":{},"finish_reason":"stop"}]}',
        'data: [DONE]',
    ]
    prov = OpenAICompatProvider("http://x/v1", "k", "gpt-4o",
                                poster=lambda url, headers, json: iter(lines))
    events = list(prov.chat([Message("user", "hi")], []))
    assert any(isinstance(e, TextDelta) and e.text == "hi" for e in events)
    assert any(isinstance(e, Done) for e in events)

def test_chat_assembles_multichunk_tool_call():
    lines = [
        'data: {"choices":[{"delta":{"tool_calls":[{"index":0,"id":"call_1","function":{"name":"run_command","arguments":""}}]}}]}',
        'data: {"choices":[{"delta":{"tool_calls":[{"index":0,"function":{"arguments":"{\\"command\\":"}}]}}]}',
        'data: {"choices":[{"delta":{"tool_calls":[{"index":0,"function":{"arguments":"\\"ls\\"}"}}]}}]}',
        'data: {"choices":[{"delta":{},"finish_reason":"tool_calls"}]}',
        'data: [DONE]',
    ]
    prov = OpenAICompatProvider("http://x/v1", "k", "gpt-4o",
                                poster=lambda url, headers, json: iter(lines))
    events = list(prov.chat([Message("user", "scan")], []))
    tcs = [e for e in events if isinstance(e, ToolCallEvent)]
    assert len(tcs) == 1
    assert tcs[0].name == "run_command"
    assert tcs[0].arguments == {"command": "ls"}
    assert any(isinstance(e, Done) and e.stop_reason == "tool_use" for e in events)
