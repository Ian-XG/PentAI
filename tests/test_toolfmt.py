from pentai.ui.toolfmt import format_command_output, looks_like_tool_schema_dump


def test_detects_tool_schema_dump_with_spaced_colons():
    # the exact failure mode: a 3B model echoing the tool schema as text
    dump = ('{ "arguments" : { "run_command" : { "type" : "function" , "name" : '
            '"Run a shell command" } , "save_note" : { "type" : "function" } } }')
    assert looks_like_tool_schema_dump(dump) is True

def test_detects_tool_schema_dump_compact_json():
    dump = '{"type":"function","name":"run_command"}{"type":"function","name":"load_playbook"}'
    assert looks_like_tool_schema_dump(dump) is True

def test_normal_answer_is_not_a_dump():
    assert looks_like_tool_schema_dump("Two open ports. Want me to enumerate the web server?") is False

def test_prose_mentioning_one_tool_is_not_a_dump():
    # mentions a tool name in prose but no schema JSON -> not flagged
    assert looks_like_tool_schema_dump(
        "I'll use run_command to scan the host and report what I find.") is False

def test_short_text_is_never_a_dump():
    assert looks_like_tool_schema_dump('{"arguments"}') is False

def test_detects_dump_dominated_by_record_tools():
    # record_service/record_finding are 2 of the 5 real agent tools (see
    # cli.py's AGENT_TOOL_NAMES) - a dump naming mostly those must still be
    # caught, not just ones mentioning run_command/save_note/load_playbook.
    dump = ('{ "arguments" : { "record_service" : { "type" : "function" } , '
            '"record_finding" : { "type" : "function" } } }')
    assert looks_like_tool_schema_dump(dump) is True

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
