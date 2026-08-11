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

def test_update_tip_none_when_current(tmp_path):
    text = f'__version__ = "{CURRENT_VERSION}"\n'
    assert update_tip(get_fn=_ok(text), cache_path=tmp_path / "cache.json") is None

def test_update_tip_mentions_versions_and_update_command(tmp_path):
    tip = update_tip(get_fn=_ok('__version__ = "42.0.0"'), cache_path=tmp_path / "cache.json")
    assert tip is not None
    assert CURRENT_VERSION in tip
    assert "42.0.0" in tip
    assert "/update" in tip

def test_update_status_text_up_to_date(tmp_path):
    text = f'__version__ = "{CURRENT_VERSION}"\n'
    out = update_status_text(get_fn=_ok(text), cache_path=tmp_path / "cache.json")
    assert "up to date" in out
    assert CURRENT_VERSION in out

def test_update_status_text_shows_upgrade_instructions(tmp_path):
    out = update_status_text(get_fn=_ok('__version__ = "9.9.9"'), cache_path=tmp_path / "cache.json")
    assert "9.9.9" in out
    assert "pip install" in out
