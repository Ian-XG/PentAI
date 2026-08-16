from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from .banner import render_sigil_rich
from .. import __version__

def capability_rows(playbooks: list[str], tools: list[str], modes: list[str]) -> list[tuple[str, str]]:
    def join(xs: list[str]) -> str:
        return ", ".join(xs) if xs else "(none)"
    return [("playbooks", join(playbooks)), ("tools", join(tools)), ("modes", join(modes))]

def render_startup(console, *, palette, provider, model, playbooks, tools, modes,
                   scope_count, session_id) -> None:
    accent = palette["accent"]
    dim = palette["dim"]
    primary = palette["primary"]
    body = Table.grid(padding=(0, 2))
    body.add_column()
    body.add_column()
    body.add_row(Text("PentAI", style=f"bold {accent}"), Text(f"v{__version__}", style=dim))
    body.add_row(Text("", style=dim), Text("", style=dim))
    for label, value in capability_rows(playbooks, tools, modes):
        body.add_row(Text(label, style=dim), Text(value, style=primary))
    body.add_row(Text("", style=dim), Text("", style=dim))
    body.add_row(Text("provider", style=dim), Text(f"{provider}:{model}", style=accent))
    body.add_row(Text("scope", style=dim), Text(str(scope_count), style=primary))
    body.add_row(Text("session", style=dim), Text(session_id, style=dim))
    body.add_row(Text("settings", style=dim), Text("pentai --settings", style=accent))
    sigil = render_sigil_rich(accent, dim)
    if console.width < 90:
        layout = Table.grid()
        layout.add_column()
        layout.add_row(sigil)
        layout.add_row(body)
    else:
        layout = Table.grid(padding=(0, 3))
        layout.add_column()
        layout.add_column()
        layout.add_row(sigil, body)
    console.print(Panel(layout, border_style=accent,
                        title="[ authorized use only ]", title_align="left"))

def render_toolcheck(console, palette, results) -> None:
    accent = palette["accent"]
    dim = palette["dim"]
    found = sum(1 for _, available in results if available)
    parts = []
    for name, available in results:
        mark = "✓" if available else "✗"
        style = accent if available else dim
        parts.append(f"[{style}]{mark} {name}[/]")
    console.print(f"[{dim}]tools[/] [bold {accent}]{found}/{len(results)}[/]  "
                 + "  ".join(parts), style=dim)
