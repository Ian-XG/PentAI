from dataclasses import dataclass, field
from typing import Iterator, Protocol

@dataclass
class Tool:
    name: str
    description: str
    parameters: dict

@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict

@dataclass
class Message:
    role: str
    content: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    tool_call_id: str | None = None

@dataclass
class TextDelta:
    text: str

@dataclass
class ToolCallEvent:
    id: str
    name: str
    arguments: dict

@dataclass
class Done:
    stop_reason: str

@dataclass
class Notice:
    """An out-of-band, user-facing message from a provider (e.g. it had to
    disable tool-calling for a model that doesn't support it). Not model output."""
    text: str

Event = TextDelta | ToolCallEvent | Done | Notice

class Provider(Protocol):
    def chat(self, messages: list[Message], tools: list[Tool],
             system: str = "") -> Iterator[Event]:
        ...
