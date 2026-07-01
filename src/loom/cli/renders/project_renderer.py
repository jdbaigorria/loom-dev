"""Rendering helpers for project-related CLI output."""

from pathlib import Path

from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table

from loom.core.exceptions import ValidationResult
from loom.utils.ui import console, print_hint, print_success

# --- Constants ---
_SECTION_LABELS = {
    "system": "System",
    "aws": "AWS",
    "project": "Project",
    "agents": "Agents",
}


def render_doctor(sections: dict[str, list[ValidationResult]]) -> None:
    """Display ``loom doctor`` results grouped by section in Rich panels."""

    all_ok = all(r.ok for results in sections.values() for r in results)

    for key, label in _SECTION_LABELS.items():
        results = sections.get(key, [])
        if not results:
            continue

        table = Table.grid(padding=(0, 2))
        table.add_column(width=2)
        table.add_column()
        table.add_column(style="dim")

        for r in results:
            icon = "[green]✅[/green]" if r.ok else "[red]✗ [/red]"
            tip = f"  → {r.tip}" if r.tip else ""
            table.add_row(icon, r.message, tip)

        section_ok = all(r.ok for r in results)
        border = "green" if section_ok else "red"
        console.print(
            Panel(table, title=f"[bold]{label}[/bold]", border_style=border, expand=False)
        )

    console.print()
    if all_ok:
        console.print("[bold green]✅ All checks passed — environment is ready.[/bold green]")
    else:
        console.print("[bold red]✗  Some checks failed. Review the results above.[/bold red]")
    console.print()


def show_preview_project(files: list, title: str, root_path: Path, format: str = "txt") -> None:
    """Print a panel listing the files created during project initialization."""
    if not files:
        return

    content = "\n".join([f"✔ {str(file.relative_to(root_path))}" for file in files])
    syntax = Syntax(content, format, theme="monokai")
    console.print()
    console.print(
        Panel(syntax, title=f"[bold yellow]📄 {title}[/bold yellow]", border_style="yellow")
    )
    print_success("Project initialized successfully")
    print_hint("Now you can create your first agent with: loom agent new <name>")
