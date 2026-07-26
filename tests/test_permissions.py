from pentai.permissions import MODES, next_mode, should_prompt_exec, should_prompt_oos

def test_modes_order():
    assert MODES == ["ask", "auto", "bypass"]

def test_next_mode_cycles():
    assert next_mode("ask") == "auto"
    assert next_mode("auto") == "bypass"
    assert next_mode("bypass") == "ask"
    assert next_mode("nonsense") == "ask"

def test_should_prompt_exec():
    assert should_prompt_exec("ask") is True
    assert should_prompt_exec("auto") is False
    assert should_prompt_exec("bypass") is False

def test_should_prompt_oos():
    assert should_prompt_oos("ask") is True
    assert should_prompt_oos("auto") is True
    assert should_prompt_oos("bypass") is False
