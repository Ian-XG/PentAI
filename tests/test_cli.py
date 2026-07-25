from pathlib import Path
from pentai.config import Config, ProviderConfig
from pentai.scope import Scope
from pentai.cli import build_agent
from pentai.agent import Agent

def test_build_agent_wires_three_tools(tmp_path: Path):
    cfg = Config(active="a", providers={"a": ProviderConfig("anthropic", "claude-opus-4", "k")})
    agent = build_agent(cfg, Scope([]), confirm=lambda p: True, session_dir=tmp_path)
    assert isinstance(agent, Agent)
    assert set(agent.tools) == {"run_command", "save_note", "load_playbook"}
