from pentai.model_advice import (RECOMMENDED, is_over_refuser, over_refusal_tip,
                                 recommended_text)

def test_over_refuser_flags_known_safety_models():
    assert is_over_refuser("gpt-oss:120b")
    assert is_over_refuser("gpt-oss:20b")
    assert is_over_refuser("llama-guard3")
    assert is_over_refuser("shieldgemma")

def test_over_refuser_does_not_flag_low_refusal_models():
    assert not is_over_refuser("hermes3")
    assert not is_over_refuser("dolphin-mixtral")
    assert not is_over_refuser("claude-opus-4")
    assert not is_over_refuser("")

def test_over_refusal_tip_mentions_switch_and_a_recommended_model():
    tip = over_refusal_tip("gpt-oss:120b")
    assert tip is not None
    assert "/model" in tip
    assert any(name.split(":")[0] in tip for name, _ in RECOMMENDED)

def test_over_refusal_tip_none_for_good_model():
    assert over_refusal_tip("hermes3") is None

def test_recommended_text_lists_curated_models_with_notes():
    txt = recommended_text()
    for name, _note in RECOMMENDED:
        assert name in txt
    assert "hermes3" in txt          # the flagship recommendation is present
    # every recommendation carries a one-line reason
    for _name, note in RECOMMENDED:
        assert note and note in txt

def test_recommended_models_are_nonempty_and_unique():
    names = [n for n, _ in RECOMMENDED]
    assert len(names) >= 3
    assert len(names) == len(set(names))
