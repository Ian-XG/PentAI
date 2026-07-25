from pentai.providers.base import Tool, ToolCall, Message, TextDelta, ToolCallEvent, Done

def test_message_defaults():
    m = Message(role="user", content="hi")
    assert m.tool_calls == []
    assert m.tool_call_id is None

def test_event_shapes():
    assert TextDelta("x").text == "x"
    assert ToolCallEvent("id1", "run_command", {"command": "ls"}).name == "run_command"
    assert Done("tool_use").stop_reason == "tool_use"
    assert ToolCall("id1", "run_command", {}).id == "id1"
    assert Tool("run_command", "run a shell command", {"type": "object"}).name == "run_command"
