from pentai.providers.base import Message, Tool, TextDelta, ToolCallEvent, Done
from pentai.agent import Agent, ToolSpec, ToolInvocation

class ScriptedProvider:
    """Yields a scripted list of event-lists, one per chat() call."""
    def __init__(self, scripts):
        self.scripts = list(scripts)
        self.calls = 0
        self.last_system = None
    def chat(self, messages, tools, system=""):
        self.last_system = system
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

def test_send_passes_system_prompt():
    prov = ScriptedProvider([[TextDelta("hi"), Done("end")]])
    agent = Agent(prov, "SYSPROMPT", {})
    list(agent.send("hi"))
    assert prov.last_system == "SYSPROMPT"

def test_send_appends_context_to_system():
    from pentai.providers.base import Message, TextDelta, Done
    from pentai.agent import Agent
    class CapturingProvider:
        def __init__(self): self.system = None
        def chat(self, messages, tools, system=""):
            self.system = system
            yield TextDelta("ok"); yield Done("end")
    prov = CapturingProvider()
    agent = Agent(prov, "BASE PROMPT", {}, context_provider=lambda: "SCOPE: 10.0.0.0/24")
    list(agent.send("hi"))
    assert "BASE PROMPT" in prov.system
    assert "SCOPE: 10.0.0.0/24" in prov.system

class LoopingProvider:
    """Always returns a tool call, never terminates on its own."""
    def __init__(self):
        self.calls = 0
    def chat(self, messages, tools, system=""):
        self.calls += 1
        yield ToolCallEvent("t1", "run_command", {"command": "ls"})
        yield Done("tool_use")

def test_agent_stops_at_max_iterations():
    tool = Tool("run_command", "run", {"type": "object"})
    spec = ToolSpec(tool, lambda args: "exit=0")
    prov = LoopingProvider()
    agent = Agent(prov, "sys", {"run_command": spec})
    list(agent.send("scan"))
    assert prov.calls <= 25

def test_tool_exception_becomes_result_and_turn_continues():
    def boom(args):
        raise ValueError("nmap blew up")
    tool = Tool("run_command", "run", {"type": "object"})
    spec = ToolSpec(tool, boom)
    prov = ScriptedProvider([
        [ToolCallEvent("t1", "run_command", {"command": "nmap x"}), Done("tool_use")],
        [TextDelta("recovered"), Done("end")],
    ])
    agent = Agent(prov, "sys", {"run_command": spec})
    out = list(agent.send("scan"))                       # must NOT raise
    inv = next(e for e in out if isinstance(e, ToolInvocation))
    assert "tool error" in inv.result.lower()
    assert "ValueError" in inv.result and "nmap blew up" in inv.result
    # the model got the error as a tool result and finished the turn
    assert any(isinstance(e, TextDelta) and e.text == "recovered" for e in out)

def test_unknown_tool_is_reported_not_crashed():
    prov = ScriptedProvider([
        [ToolCallEvent("t1", "does_not_exist", {}), Done("tool_use")],
        [TextDelta("ok"), Done("end")],
    ])
    agent = Agent(prov, "sys", {})
    out = list(agent.send("go"))
    inv = next(e for e in out if isinstance(e, ToolInvocation))
    assert "unknown tool" in inv.result.lower()
