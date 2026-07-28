from pentai.ui.toolfmt import format_command_output

def test_clean_success_hides_exit_and_empty_stderr():
    r = "exit_code=0\n--- stdout ---\n216.198.79.65\n64.29.17.1\n--- stderr ---\n"
    assert format_command_output(r) == "216.198.79.65\n64.29.17.1"

def test_nonzero_shows_exit_and_stderr():
    r = "exit_code=127\n--- stdout ---\n\n--- stderr ---\n/bin/sh: whatweb: command not found"
    out = format_command_output(r)
    assert "stderr: /bin/sh: whatweb: command not found" in out
    assert "[exit code 127]" in out

def test_no_output():
    assert format_command_output("exit_code=0\n--- stdout ---\n\n--- stderr ---\n") == "(no output)"

def test_unknown_format_passthrough():
    assert format_command_output("just a string") == "just a string"
