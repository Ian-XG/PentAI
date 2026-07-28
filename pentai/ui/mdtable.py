from rich import box
from rich.console import Console, ConsoleOptions, RenderResult
from rich.markdown import Markdown, TableElement
from rich.table import Table


class _BorderedTable(TableElement):
    """TableElement variant that adds vertical column separators and a header
    rule (no per-row horizontal lines) instead of rich's default
    header-underline-only table."""

    def __rich_console__(
        self, console: Console, options: ConsoleOptions
    ) -> RenderResult:
        table = Table(
            box=box.MINIMAL,
            pad_edge=False,
            style="markdown.table.border",
            show_edge=True,
            show_lines=False,
            collapse_padding=True,
        )

        if self.header is not None and self.header.row is not None:
            for column in self.header.row.cells:
                heading = column.content.copy()
                heading.stylize("markdown.table.header")
                table.add_column(heading)

        if self.body is not None:
            for row in self.body.rows:
                row_content = [element.content for element in row.cells]
                table.add_row(*row_content)

        yield table


class TableMarkdown(Markdown):
    elements = {**Markdown.elements, "table_open": _BorderedTable}


def md(text: str) -> TableMarkdown:
    return TableMarkdown(text)
