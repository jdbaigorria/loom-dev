from typer import Argument, Exit, Typer

from loom.core.paths import build_workspace_paths
from loom.services.stats_service import aggregate, load_stats
from loom.utils.ui import print_error, print_warning

from ..renders.agent_renderer import render_agent_stats

app: Typer = Typer()


@app.callback(invoke_without_command=True)
def agent_stats(
    name: str = Argument(..., help="Name of the agent"),
):
    """Show historical metrics for an agent from .loom/stats/{name}.jsonl."""
    stats_file = build_workspace_paths().agent_stats_file(name)
    records = load_stats(stats_file)

    if not records:
        print_warning(
            f"No stats found for [bold]{name}[/bold]."
            " Run the agent at least once to generate metrics."
        )
        raise Exit(0)

    try:
        summary = aggregate(records)
        render_agent_stats(name, summary)
    except Exception as e:
        print_error(f"Error reading stats: {e}")
        raise Exit(1)
