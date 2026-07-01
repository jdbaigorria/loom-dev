import os
import subprocess

from typer import Argument, Exit, Typer

from loom.core.exceptions import AgentNotFoundError
from loom.core.paths import build_workspace_paths
from loom.utils.ui import print_error, print_hint

app: Typer = Typer()


@app.callback(invoke_without_command=True)
def edit_agent(
    name: str = Argument(..., help="Name of the agent to edit"),
):
    """Open the agent YAML config in the system editor."""
    try:
        yaml_path = build_workspace_paths().resolve_agent_yaml(name)
        editor = os.environ.get("EDITOR") or os.environ.get("VISUAL") or "vi"
        print_hint(f"Opening [white]{yaml_path.name}[/white] in [bold]{editor}[/bold]...")
        subprocess.run([editor, str(yaml_path)])
    except AgentNotFoundError:
        print_error(f"Agent '{name}' not found. Run: loom agent new {name}")
        raise Exit(1)
    except Exception as e:
        print_error(f"Error opening editor: {e}")
        raise Exit(1)
