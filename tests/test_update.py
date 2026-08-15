import threading
import time

from pentai.update import (CURRENT_VERSION, is_newer, fetch_latest_version,
                           check_for_update, update_tip, update_status_text)

def _ok(text):
    return lambda url, timeout: text

def _fail(url, timeout):
    raise ConnectionError("offline")

def test_is_newer_compares_numeric_parts():
    assert is_newer("0.2.0", "0.1.0")
    assert not is_newer("0.1.0", "0.1.0")
    assert not is_newer("0.1.0", "0.2.0")
    assert is_newer("0.10.0", "0.9.0")   # numeric, not lexicographic

def test_fetch_latest_version_parses_dunder_version():
    text = 'some header\n__version__ = "1.2.3"\nmore code\n'
    assert fetch_latest_version(get_fn=_ok(text)) == "1.2.3"

def test_fetch_latest_version_returns_none_on_network_failure():
    assert fetch_latest_version(get_fn=_fail) is None

def test_fetch_latest_version_returns_none_when_pattern_missing():
    assert fetch_latest_version(get_fn=_ok("no version here")) is None

def test_check_for_update_returns_none_when_current(tmp_path):
    text = f'__version__ = "{CURRENT_VERSION}"\n'
    result = check_for_update(get_fn=_ok(text), cache_path=tmp_path / "cache.json")
    assert result is None

def test_check_for_update_returns_newer_version(tmp_path):
    result = check_for_update(get_fn=_ok('__version__ = "99.0.0"\n'),
                              cache_path=tmp_path / "cache.json")
    assert result == "99.0.0"

def test_check_for_update_caches_and_skips_network_within_interval(tmp_path):
    cache_path = tmp_path / "cache.json"
    calls = {"n": 0}
    def counting_get(url, timeout):
        calls["n"] += 1
        return '__version__ = "5.0.0"'
    r1 = check_for_update(get_fn=counting_get, cache_path=cache_path, now=1000)
    r2 = check_for_update(get_fn=counting_get, cache_path=cache_path, now=1000 + 60)
    assert r1 == r2 == "5.0.0"
    assert calls["n"] == 1

def test_check_for_update_rechecks_after_interval_elapses(tmp_path):
    cache_path = tmp_path / "cache.json"
    calls = {"n": 0}
    def counting_get(url, timeout):
        calls["n"] += 1
        return '__version__ = "5.0.0"'
    check_for_update(get_fn=counting_get, cache_path=cache_path, now=1000)
    check_for_update(get_fn=counting_get, cache_path=cache_path, now=1000 + 25 * 60 * 60)
    assert calls["n"] == 2

def test_check_for_update_force_bypasses_cache(tmp_path):
    cache_path = tmp_path / "cache.json"
    calls = {"n": 0}
    def counting_get(url, timeout):
        calls["n"] += 1
        return '__version__ = "5.0.0"'
    check_for_update(get_fn=counting_get, cache_path=cache_path, now=1000)
    check_for_update(get_fn=counting_get, cache_path=cache_path, now=1001, force=True)
    assert calls["n"] == 2

def test_check_for_update_survives_network_failure_silently(tmp_path):
    assert check_for_update(get_fn=_fail, cache_path=tmp_path / "cache.json") is None

def test_update_tip_none_when_cache_empty(tmp_path):
    # nothing cached yet - must not block on the network to find out, so it
    # can only say "nothing to report" this run. spawn is a no-op here (never
    # actually runs the background refresh) so the assertion is deterministic
    # regardless of the real threading.Thread's scheduling - a fast enough
    # background fetch racing the synchronous cache read is exercised by
    # test_update_tip_background_refresh_populates_cache_for_next_call
    # instead, with an explicitly synchronous spawn.
    assert update_tip(get_fn=_ok('__version__ = "42.0.0"'),
                      cache_path=tmp_path / "cache.json",
                      spawn=lambda fn: None) is None

def test_update_tip_never_blocks_on_a_slow_network(tmp_path):
    def slow_get(url, timeout):
        time.sleep(0.5)
        return '__version__ = "1.0.0"'
    start = time.time()
    result = update_tip(get_fn=slow_get, cache_path=tmp_path / "cache.json")
    assert time.time() - start < 0.2   # returned long before slow_get finished
    assert result is None              # nothing cached yet

def test_update_tip_reads_a_prewarmed_cache_synchronously(tmp_path):
    cache_path = tmp_path / "cache.json"
    check_for_update(get_fn=_ok('__version__ = "42.0.0"'), cache_path=cache_path)
    tip = update_tip(get_fn=_fail, cache_path=cache_path)  # network unused - cache is fresh
    assert tip is not None
    assert CURRENT_VERSION in tip
    assert "42.0.0" in tip
    assert "/update" in tip

def test_update_tip_none_when_cache_is_current(tmp_path):
    cache_path = tmp_path / "cache.json"
    text = f'__version__ = "{CURRENT_VERSION}"\n'
    check_for_update(get_fn=_ok(text), cache_path=cache_path)
    assert update_tip(get_fn=_fail, cache_path=cache_path) is None

def test_update_tip_synchronous_spawn_reflects_a_fresh_fetch(tmp_path):
    tip = update_tip(get_fn=_ok('__version__ = "42.0.0"'), cache_path=tmp_path / "cache.json",
                     spawn=lambda fn: fn())
    assert tip is not None
    assert CURRENT_VERSION in tip
    assert "42.0.0" in tip
    assert "/update" in tip

def test_update_tip_background_refresh_populates_cache_for_next_call(tmp_path):
    cache_path = tmp_path / "cache.json"
    calls = {"n": 0}
    def counting_get(url, timeout):
        calls["n"] += 1
        return '__version__ = "7.0.0"'
    synchronous_spawn = lambda fn: fn()
    update_tip(get_fn=counting_get, cache_path=cache_path, spawn=synchronous_spawn)
    tip2 = update_tip(get_fn=counting_get, cache_path=cache_path, spawn=synchronous_spawn)
    assert calls["n"] == 1              # cache was fresh on the 2nd call - no re-fetch
    assert "7.0.0" in tip2

def test_default_spawn_runs_fn_on_a_background_thread():
    # isolates _default_spawn itself (the real threading.Thread wiring) from
    # update_tip's logic, and waits on an Event instead of polling with a
    # fixed sleep budget - deterministic regardless of scheduler/CI load,
    # unlike a "poll N times then give up" loop that can lose the race.
    from pentai.update import _default_spawn
    ran = threading.Event()
    _default_spawn(ran.set)
    assert ran.wait(timeout=2), "background thread never ran fn"

def test_update_tip_default_spawn_does_not_crash_without_a_real_network(tmp_path):
    # exercises update_tip with its real default (threading.Thread) spawn -
    # must not raise. No assertion on timing/outcome: whether the background
    # thread happens to finish before this returns is scheduler-dependent and
    # both outcomes are correct (that determinism is covered separately by
    # test_default_spawn_runs_fn_on_a_background_thread above and the
    # explicit-synchronous-spawn tests elsewhere in this file).
    result = update_tip(get_fn=_ok('__version__ = "3.0.0"'), cache_path=tmp_path / "cache.json")
    assert result is None or "3.0.0" in result

def test_update_status_text_up_to_date(tmp_path):
    text = f'__version__ = "{CURRENT_VERSION}"\n'
    out = update_status_text(get_fn=_ok(text), cache_path=tmp_path / "cache.json")
    assert "up to date" in out
    assert CURRENT_VERSION in out

def test_update_status_text_shows_upgrade_instructions(tmp_path):
    out = update_status_text(get_fn=_ok('__version__ = "9.9.9"'), cache_path=tmp_path / "cache.json")
    assert "9.9.9" in out
    assert "pip install" in out

def _completed(cmd, returncode=0, stdout="", stderr=""):
    import subprocess
    return subprocess.CompletedProcess(cmd, returncode, stdout=stdout, stderr=stderr)

def test_update_instructions_editable_install(monkeypatch, tmp_path):
    from pentai import update as update_mod
    monkeypatch.setattr(update_mod, "_repo_root", lambda: tmp_path)
    (tmp_path / ".git").mkdir()
    instr = update_mod.update_instructions()
    assert "git pull" in instr and str(tmp_path) in instr

def test_update_instructions_non_editable_install(monkeypatch, tmp_path):
    from pentai import update as update_mod
    monkeypatch.setattr(update_mod, "_repo_root", lambda: tmp_path)  # no .git
    instr = update_mod.update_instructions()
    assert instr == "pip install --upgrade git+https://github.com/Ian-XG/PentAI.git"

def test_perform_update_editable_runs_git_pull_then_pip_install(monkeypatch, tmp_path):
    from pentai import update as update_mod
    monkeypatch.setattr(update_mod, "_repo_root", lambda: tmp_path)
    (tmp_path / ".git").mkdir()
    calls = []
    def fake_run(cmd, cwd):
        calls.append((cmd, cwd))
        return _completed(cmd, stdout="Already up to date.\n")
    ok, msg = update_mod.perform_update(run_fn=fake_run)
    assert ok is True
    assert calls[0] == (["git", "pull"], tmp_path)
    assert calls[1] == (["pip", "install", "-e", ".[dev]"], tmp_path)
    assert "Already up to date" in msg

def test_perform_update_editable_reports_git_pull_failure(monkeypatch, tmp_path):
    from pentai import update as update_mod
    monkeypatch.setattr(update_mod, "_repo_root", lambda: tmp_path)
    (tmp_path / ".git").mkdir()
    def fake_run(cmd, cwd):
        return _completed(cmd, returncode=1, stderr="local changes would be overwritten")
    ok, msg = update_mod.perform_update(run_fn=fake_run)
    assert ok is False
    assert "local changes" in msg

def test_perform_update_editable_reports_pip_install_failure(monkeypatch, tmp_path):
    from pentai import update as update_mod
    monkeypatch.setattr(update_mod, "_repo_root", lambda: tmp_path)
    (tmp_path / ".git").mkdir()
    def fake_run(cmd, cwd):
        if cmd[0] == "git":
            return _completed(cmd, stdout="Updating abc..def\n")
        return _completed(cmd, returncode=1, stderr="pip broke")
    ok, msg = update_mod.perform_update(run_fn=fake_run)
    assert ok is False
    assert "pip broke" in msg

def test_perform_update_non_editable_uses_pip_install_upgrade(monkeypatch, tmp_path):
    from pentai import update as update_mod
    monkeypatch.setattr(update_mod, "_repo_root", lambda: tmp_path)  # no .git
    calls = []
    def fake_run(cmd, cwd):
        calls.append((cmd, cwd))
        return _completed(cmd)
    ok, msg = update_mod.perform_update(run_fn=fake_run)
    assert ok is True
    assert calls == [(["pip", "install", "--upgrade", "git+https://github.com/Ian-XG/PentAI.git"], None)]
