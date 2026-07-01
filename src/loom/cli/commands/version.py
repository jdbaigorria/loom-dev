import sys
from importlib.metadata import PackageNotFoundError, version

from typer import Typer

from loom.utils.ui import console

app: Typer = Typer()

_DEPS = ["strands-agents", "strands-agents-evals", "omegaconf", "pydantic", "typer", "rich"]


@app.callback(invoke_without_command=True)
def show_version():
    """Show version of loom and key dependencies."""
    from rich.table import Table

    table = Table.grid(padding=(0, 3))
    table.add_column(style="cyan")
    table.add_column()

    def _ver(pkg: str) -> str:
        try:
            return version(pkg)
        except PackageNotFoundError:
            return "[dim]not installed[/dim]"

    table.add_row("[bold]loom[/bold]", _ver("loom"))
    table.add_row("[dim]Python[/dim]", sys.version.split()[0])
    for dep in _DEPS:
        table.add_row(f"[dim]{dep}[/dim]", _ver(dep))

    console.print()
    console.print(table)
    console.print()
