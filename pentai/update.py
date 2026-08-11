"""Update notifications. PentAI is installed from git, not PyPI, so "latest
version" means whatever __version__ is on origin/main - checked via
raw.githubusercontent.com (a CDN, not the rate-limited GitHub API) so no
auth or release/tag process is needed. Bumping pentai/__init__.py's
__version__ and pushing to main is all a release requires; every installed
copy picks it up on its next check."""

import json
import re
import time
from pathlib import Path
from typing import Callable

from . import __version__ as CURRENT_VERSION

_VERSION_URL = "https://raw.githubusercontent.com/Ian-XG/PentAI/main/pentai/__init__.py"
_REPO_URL = "https://github.com/Ian-XG/PentAI"
_CACHE_PATH = Path.home() / ".pentai" / "update_check.json"
_CHECK_INTERVAL = 24 * 60 * 60  # seconds between unforced checks

GetFn = Callable[[str, float], str]

def _default_get(url: str, timeout: float) -> str:
    import httpx
    resp = httpx.get(url, timeout=timeout, follow_redirects=True)
    resp.raise_for_status()
    return resp.text

def _parse_version(text: str) -> tuple[int, ...]:
    return tuple(int(p) for p in re.findall(r"\d+", text)) or (0,)

def is_newer(remote: str, local: str = CURRENT_VERSION) -> bool:
    return _parse_version(remote) > _parse_version(local)

def fetch_latest_version(get_fn: GetFn = _default_get, timeout: float = 2.0) -> str | None:
    """The published __version__ on main, or None on any network/parse failure -
    an update check must never block or crash startup."""
    try:
        text = get_fn(_VERSION_URL, timeout)
    except Exception:
        return None
    m = re.search(r'__version__\s*=\s*"([^"]+)"', text)
    return m.group(1) if m else None

def _load_cache(path: Path) -> dict:
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return {}

def _save_cache(data: dict, path: Path) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data))
    except OSError:
        pass

def check_for_update(*, force: bool = False, now: float | None = None,
                     get_fn: GetFn = _default_get,
                     cache_path: Path = _CACHE_PATH) -> str | None:
    """The newer remote version string if one is available, else None. Cached
    for _CHECK_INTERVAL so normal startups skip the network; /update passes
    force=True to bypass the cache."""
    now = time.time() if now is None else now
    cache = _load_cache(cache_path)
    if not force and cache.get("checked_at") and now - cache["checked_at"] < _CHECK_INTERVAL:
        latest = cache.get("latest")
        return latest if latest and is_newer(latest) else None
    latest = fetch_latest_version(get_fn=get_fn)
    _save_cache({"checked_at": now, "latest": latest or cache.get("latest")}, cache_path)
    return latest if latest and is_newer(latest) else None

def update_instructions() -> str:
    """How to upgrade, tailored to how this copy was installed."""
    import pentai
    repo_root = Path(pentai.__file__).resolve().parent.parent
    if (repo_root / ".git").is_dir():
        return f"cd {repo_root} && git pull && pip install -e .[dev]"
    return f"pip install --upgrade git+{_REPO_URL}.git"

def update_tip(*, force: bool = False, get_fn: GetFn = _default_get,
              cache_path: Path = _CACHE_PATH) -> str | None:
    """One-line startup notice, or None if already current."""
    latest = check_for_update(force=force, get_fn=get_fn, cache_path=cache_path)
    if latest is None:
        return None
    return f"update available: v{CURRENT_VERSION} -> v{latest} - run /update for instructions"

def update_status_text(get_fn: GetFn = _default_get, cache_path: Path = _CACHE_PATH) -> str:
    """Full /update output: forces a fresh check."""
    latest = check_for_update(force=True, get_fn=get_fn, cache_path=cache_path)
    if latest is None:
        return f"pentai v{CURRENT_VERSION} - up to date"
    return (f"pentai v{CURRENT_VERSION} -> v{latest} available\n"
            f"  {update_instructions()}")
