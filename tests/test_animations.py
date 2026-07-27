import random
from pentai.ui.animations import run_once, glitch_frames

def test_run_once_invokes_only_first_time():
    calls = []
    once = run_once(lambda: calls.append(1))
    once(); once(); once()
    assert calls == [1]

def test_glitch_frames_shape_and_final():
    frames = glitch_frames("PENTAI", frames=3, rng=random.Random(0))
    assert len(frames) == 4                 # 3 glitched + 1 clean
    assert frames[-1] == "PENTAI"           # settles on the clean text
    assert all(len(f) == len("PENTAI") for f in frames)  # length preserved

def test_glitch_frames_preserves_whitespace_positions():
    text = "P E N"
    frames = glitch_frames(text, frames=4, rng=random.Random(1))
    for f in frames[:-1]:
        for i, ch in enumerate(text):
            if ch == " ":
                assert f[i] == " "          # spaces never corrupted
