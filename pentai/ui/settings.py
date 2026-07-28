from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from ..onboarding import PROVIDER_CHOICES

def render_provider_menu(console, palette: dict, current_active: str | None) -> None:
    """Polished provider-picker menu: icon | number | name | description, with the
    active provider tagged, matching the phosphor-green panel/table style used by
    ui/startup.py::render_startup."""
    accent = palette["accent"]
    dim = palette["dim"]
    primary = palette["primary"]

    menu = Table.grid(padding=(0, 1))
    menu.add_column()  # icon
    menu.add_column()  # number
    menu.add_column()  # name
    menu.add_column()  # description
    for i, c in enumerate(PROVIDER_CHOICES, 1):
        is_current = c.name == current_active
        name_style = f"bold {accent}" if is_current else primary
        desc = Text(c.label, style=dim)
        if is_current:
            desc = Text.assemble(desc, Text("  ● current", style=f"bold {accent}"))
        menu.add_row(
            Text(c.icon, style=accent),
            Text(f"{i})", style=dim),
            Text(c.name, style=name_style),
            desc,
        )

    body = Table.grid()
    body.add_column()
    body.add_row(menu)
    body.add_row(Text(""))
    body.add_row(Text("Enter a number to choose  ·  Ctrl-C to cancel / exit", style=dim))

    console.print(Panel(body, title="PentAI · Settings", title_align="left", border_style=accent))
