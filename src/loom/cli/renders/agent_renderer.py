"""Rendering helpers for agent-related CLI output."""

from pathlib import Path

from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table

from loom.core.exceptions import ValidationResult
from loom.schemas.config.agent_summary import AgentSummary
from loom.utils.ui import console, print_success


def render_agent_validation(name: str, results: list[ValidationResult]) -> None:
    """Display agent validation results in a Rich panel."""
    table = Table.grid(padding=(0, 2))
    table.add_column(width=2)
    table.add_column()
    table.add_column(style="dim")

    for r in results:
        icon = "[green]✅[/green]" if r.ok else "[red]✗ [/red]"
        tip = f"  → {r.tip}" if r.tip else ""
        table.add_row(icon, r.message, tip)

    all_ok = all(r.ok for r in results)
    border = "green" if all_ok else "red"
    status = "[green]OK[/green]" if all_ok else "[red]ERRORES ENCONTRADOS[/red]"

    console.print()
    console.print(
        Panel(
            table,
            title=f"[bold cyan]🔍 Validate: [white]{name}[/white] — {status}[/bold cyan]",
            border_style=border,
            expand=False,
        )
    )
    console.print()


def render_agent_stats(name: str, summary: dict) -> None:
    """Display historical agent metrics in a Rich panel."""
    table = Table.grid(padding=(0, 2))
    table.add_column(style="dim")
    table.add_column()

    table.add_row("Invocations", f"[bold cyan]{summary['invocations']}[/bold cyan]")

    if summary.get("last_invocation"):
        table.add_row("Last invocation", f"[white]{summary['last_invocation']}[/white]")

    table.add_row("", "")  # spacer

    table.add_row(
        "Total tokens",
        f"in=[green]{summary['total_input_tokens']}[/green]  "
        f"out=[yellow]{summary['total_output_tokens']}[/yellow]  "
        f"total=[white]{summary['total_tokens']}[/white]",
    )
    table.add_row(
        "Avg tokens / call",
        f"in=[green]{summary['avg_input_tokens']}[/green]  "
        f"out=[yellow]{summary['avg_output_tokens']}[/yellow]",
    )
    table.add_row(
        "Avg response time",
        f"[white]{summary['avg_response_time_ms']} ms[/white]",
    )
    table.add_row(
        "System prompt tokens",
        f"[dim]{summary.get('system_prompt_tokens', 0)} (estimated)[/dim]",
    )

    top_tools = summary.get("top_tools", [])
    if top_tools:
        tools_str = "  ".join(f"[cyan]{tool}[/cyan] ({count})" for tool, count in top_tools)
        table.add_row("Top tools", tools_str)

    console.print()
    console.print(
        Panel(
            table,
            title=f"[bold magenta]📊 Stats: [white]{name}[/white][/bold magenta]",
            border_style="magenta",
            expand=False,
        )
    )
    console.print()


# Used by: loom agent list
def render_agents_table(agents: list[AgentSummary]) -> None:
    """Render all agents as a Rich table. Used by ``loom agent list``."""
    table = Table(title="🧵 LOOM Agents")
    table.add_column("Agent Name", style="cyan", no_wrap=True)
    table.add_column("Model", style="blue")
    table.add_column("Description", style="dim", overflow="fold")
    table.add_column("File", style="dim", overflow="fold")

    for agent in agents:
        if agent.status == "ok":
            style = "dim" if agent.filename == "agent.yml" else "bold"
            table.add_row(
                agent.name,
                agent.model,
                agent.description,
                f"[{style}]{agent.filename}[/]",
            )
        elif agent.status == "missing":
            table.add_row(
                agent.name,
                "[yellow]—[/yellow]",
                "[yellow]Missing[/yellow]",
                f"[yellow]No agent.yml or {agent.name}.yml found[/yellow]",
            )
        else:  # error
            table.add_row(
                agent.name,
                "[red]—[/red]",
                "[red]Error[/red]",
                f"[red]Invalid YAML: {agent.error_msg}[/red]",
            )

    console.print(table)


def render_agent_yaml(content: str, path: Path, name: str) -> None:
    """Display the raw YAML configuration of an agent with syntax highlighting."""
    syntax = Syntax(
        content,
        lexer="yaml",
        theme="monokai",
        line_numbers=True,
        word_wrap=True,
        background_color="default",
    )

    console.print(
        f"\n[bold magenta]📄 Configuration for agent: [white]{name}[/white][/bold magenta]"
    )
    console.print(f"[dim]Path: {str(path)}[/dim]\n")
    console.print(syntax)
    console.print()


def show_preview_agent(files: list, title: str, root_path: Path, format: str = "txt") -> None:
    """Print a panel listing the files created for a new agent."""
    if not files:
        return

    content = "\n".join([f"✔ {str(file.relative_to(root_path))}" for file in files])
    syntax = Syntax(content, format, theme="monokai")
    console.print()
    console.print(
        Panel(syntax, title=f"[bold yellow]📄 {title}[/bold yellow]", border_style="yellow")
    )
    print_success(f"Agent [white]{root_path.name}[/white] created successfully!")
