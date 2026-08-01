from dataclasses import dataclass
from typing import Callable, Iterator
from .providers.base import (Provider, Message, Tool, ToolCall,
                             TextDelta, ToolCallEvent, Done, Notice)

@dataclass
class ToolSpec:
    tool: Tool
    run: Callable[[dict], str]

@dataclass
class ToolInvocation:
    name: str
    arguments: dict
    result: str

AgentEvent = TextDelta | ToolInvocation | Notice

class Agent:
    def __init__(self, provider: Provider, system_prompt: str,
                 tools: dict[str, ToolSpec], history: list[Message] | None = None,
                 context_provider: Callable[[], str] | None = None):
        self.provider = provider
        self.system_prompt = system_prompt
        self.tools = tools
        self.history: list[Message] = history if history is not None else []
        self._tool_defs: list[Tool] = [s.tool for s in tools.values()]
        self.context_provider = context_provider

    MAX_ITERATIONS = 25

    def send(self, user_text: str) -> Iterator[AgentEvent]:
        self.history.append(Message("user", user_text))
        system = self.system_prompt
        if self.context_provider is not None:
            system = f"{system}\n\n{self.context_provider()}"
        for _ in range(self.MAX_ITERATIONS):
            text_parts: list[str] = []
            pending: list[ToolCall] = []
            for ev in self.provider.chat(self.history, self._tool_defs, system):
                if isinstance(ev, TextDelta):
                    text_parts.append(ev.text)
                    yield ev
                elif isinstance(ev, ToolCallEvent):
                    pending.append(ToolCall(ev.id, ev.name, ev.arguments))
                elif isinstance(ev, Notice):
                    yield ev
                elif isinstance(ev, Done):
                    pass
            assistant_text = "".join(text_parts)
            self.history.append(Message("assistant", assistant_text, tool_calls=pending))
            if not pending:
                return
            for call in pending:
                spec = self.tools.get(call.name)
                result = spec.run(call.arguments) if spec else f"[unknown tool: {call.name}]"
                self.history.append(Message("tool", result, tool_call_id=call.id))
                yield ToolInvocation(call.name, call.arguments, result)
