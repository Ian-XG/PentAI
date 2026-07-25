from pentai.providers.base import Message, Tool, TextDelta, ToolCallEvent, Done
from pentai.agent import Agent, ToolSpec, ToolInvocation

class ScriptedProvider:
    """Yields a scripted list of event-lists, one per chat() call."""
    def __init__(self, scripts):
        self.scripts = list(scripts)
        self.calls = 0
    def chat(self, messages, tools):
        script = self.scripts[self.calls]
        self.calls += 1
        yield from script

def test_plain_text_turn():
    prov = ScriptedProvider([[TextDelta("hello"), Done("end")]])
    agent = Agent(prov, "sys", {})
    out = list(agent.send("hi"))
    assert any(isinstance(e, TextDelta) and e.text == "hello" for e in out)

def test_tool_call_then_final_answer():
    tool = Tool("run_command", "run", {"type": "object"})
    calls = []
    spec = ToolSpec(tool, lambda args: calls.append(args) or "exit=0")
    prov = ScriptedProvider([
        [ToolCallEvent("t1", "run_command", {"command": "ls"}), Done("tool_use")],
        [TextDelta("done"), Done("end")],
    ])
    agent = Agent(prov, "sys", {"run_command": spec})
    out = list(agent.send("scan"))
    assert calls == [{"command": "ls"}]
    assert any(isinstance(e, ToolInvocation) and e.result == "exit=0" for e in out)
    assert any(isinstance(e, TextDelta) and e.text == "done" for e in out)
