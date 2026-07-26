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

def test_provider_ready_true_with_key():
    from pentai.config import Config, ProviderConfig
    from pentai.cli import provider_ready
    cfg = Config(active="a", providers={"a": ProviderConfig("anthropic", "m", "sk-x")})
    assert provider_ready(cfg) is True

def test_provider_ready_false_without_key():
    from pentai.config import Config, ProviderConfig
    from pentai.cli import provider_ready
    cfg = Config(active="a", providers={"a": ProviderConfig("anthropic", "m")})
    assert provider_ready(cfg) is False

def test_provider_ready_true_for_keyless_local(monkeypatch):
    # ollama local has no api_key and no api_key_env -> considered ready
    from pentai.config import Config, ProviderConfig
    from pentai.cli import provider_ready
    cfg = Config(active="o",
                 providers={"o": ProviderConfig("openai_compat", "llama3.1",
                                                 base_url="http://localhost:11434/v1")})
    assert provider_ready(cfg) is True

def test_apply_mode_command_cycles_and_sets():
    from pentai.cli import apply_mode_command
    assert apply_mode_command("ask", []) == "auto"      # cycle
    assert apply_mode_command("ask", ["bypass"]) == "bypass"  # set
    assert apply_mode_command("ask", ["nonsense"]) == "ask"   # invalid -> unchanged
