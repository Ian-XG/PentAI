import httpx
from pentai.providers.base import Message, Tool, TextDelta, ToolCallEvent, Done, Notice
from pentai.providers.openai_compat import (build_payload, parse_sse_chunk,
                                            OpenAICompatProvider, list_models)

def test_list_models_parses_openai_shape():
    captured = {}
    def getter(url, headers):
        captured["url"] = url
        return {"object": "list", "data": [{"id": "llama2:latest"}, {"id": "gpt-oss:20b"}, {}]}
    models = list_models("http://localhost:11434/v1", None, getter=getter)
    assert models == ["llama2:latest", "gpt-oss:20b"]  # entry without id is skipped
    assert captured["url"] == "http://localhost:11434/v1/models"

def test_list_models_sends_bearer_when_key():
    seen = {}
    list_models("http://x/v1", "secret", getter=lambda u, h: (seen.update(h) or {"data": []}))
    assert seen["Authorization"] == "Bearer secret"

def test_set_model_resets_tools_latch():
    prov = OpenAICompatProvider("http://x/v1", None, "old")
    prov._tools_unsupported = True
    prov.set_model("new")
    assert prov.model == "new" and prov._tools_unsupported is False

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

def test_chat_retries_without_tools_on_400():
    # a local model that rejects the `tools` param (Ollama returns 400); we should
    # transparently retry as a plain chat so the model still works.
    chat_lines = [
        'data: {"choices":[{"delta":{"content":"hi there"}}]}',
        'data: {"choices":[{"delta":{},"finish_reason":"stop"}]}',
        'data: [DONE]',
    ]
    calls = []
    def poster(url, headers, json):
        calls.append("tools" in json)
        if "tools" in json:
            resp = httpx.Response(400, request=httpx.Request("POST", url))
            raise httpx.HTTPStatusError("bad request", request=resp.request, response=resp)
        return iter(chat_lines)

    prov = OpenAICompatProvider("http://localhost:11434/v1", None,
                                "llama2-uncensored", poster=poster)
    tools = [Tool("run_command", "run", {"type": "object"})]
    events = list(prov.chat([Message("user", "hi")], tools))
    assert calls == [True, False]
    assert any(isinstance(e, TextDelta) and e.text == "hi there" for e in events)
    # user is told once, on the turn tools got dropped
    assert sum(isinstance(e, Notice) for e in events) == 1

def test_chat_stops_sending_tools_after_first_400():
    # after learning tools are unsupported, later turns skip them entirely (no
    # wasted 400 round-trip) and emit no further Notice.
    chat_lines = ['data: {"choices":[{"delta":{"content":"ok"}}]}',
                  'data: {"choices":[{"delta":{},"finish_reason":"stop"}]}', 'data: [DONE]']
    calls = []
    def poster(url, headers, json):
        calls.append("tools" in json)
        if "tools" in json:
            resp = httpx.Response(400, request=httpx.Request("POST", url))
            raise httpx.HTTPStatusError("bad request", request=resp.request, response=resp)
        return iter(chat_lines)
    prov = OpenAICompatProvider("http://x/v1", None, "m", poster=poster)
    tools = [Tool("run_command", "run", {"type": "object"})]
    list(prov.chat([Message("user", "hi")], tools))       # turn 1: 400 then retry
    second = list(prov.chat([Message("user", "again")], tools))  # turn 2: no tools sent
    assert calls == [True, False, False]
    assert not any(isinstance(e, Notice) for e in second)

def test_chat_does_not_retry_400_without_tools():
    def poster(url, headers, json):
        resp = httpx.Response(400, request=httpx.Request("POST", url))
        raise httpx.HTTPStatusError("bad request", request=resp.request, response=resp)
    prov = OpenAICompatProvider("http://x/v1", None, "m", poster=poster)
    try:
        list(prov.chat([Message("user", "hi")], []))
        assert False, "expected HTTPStatusError to propagate"
    except httpx.HTTPStatusError:
        pass
