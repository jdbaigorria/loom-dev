"""CLI commands for declarative multi-agent workflows (``loom workflow ...``)."""

from uuid import uuid4

from rich.prompt import Prompt
from typer import Argument, Exit, Option, Typer

from loom.core.exceptions import LoomError, WorkflowError
from loom.core.loaders.app import resolve_env
from loom.core.loaders.workflow import get_workflow_config
from loom.core.paths import build_workspace_paths, resolve_existing_workflow_yaml
from loom.dev import run_dev
from loom.schemas.context import LoomSession
from loom.utils.ui import console, print_error, print_hint, print_success

app: Typer = Typer(help="Run and inspect multi-agent workflows")


@app.command("list")
def list_workflows() -> None:
    """List the workflows defined under ``warp/workflows/``."""
    ws = build_workspace_paths()
    if not ws.workflows_dir.is_dir():
        print_hint("No workflows directory yet. Create one at warp/workflows/<name>.yml")
        return
    files = sorted(p.stem for p in ws.workflows_dir.glob("*.yml"))
    if not files:
        print_hint("No workflows found. Create one at warp/workflows/<name>.yml")
        return
    for name in files:
        console.print(f"  • [white]{name}[/white]")


@app.command("validate")
def validate_workflow(
    name: str = Argument(..., help="Name of the workflow to validate"),
) -> None:
    """Validate a workflow YAML without running it."""
    ws = build_workspace_paths()
    try:
        config = get_workflow_config(resolve_existing_workflow_yaml(ws, name))
    except WorkflowError as e:
        print_error(str(e))
        if e.tip:
            print_hint(e.tip)
        raise Exit(1)

    detail = (
        f"{len(config.nodes)} node(s)"
        if config.type == "graph"
        else f"{len(config.agents)} agent(s)"
    )
    print_success(f"Workflow '{name}' is valid (type={config.type}, {detail}).")


@app.command("run")
def run_workflow(
    name: str = Argument(..., help="Name of the workflow to run"),
    message: str = Option(None, "--message", "-m", help="Single-shot message for the workflow"),
    env: str = Option(None, "--env", "-e", help="Environment profile. Overrides LOOM_ENV"),
) -> None:
    """Run a workflow once (``-m``) or interactively."""
    active_env = env or resolve_env()
    print_hint(f"Booting up workflow [white]{name}[/white] [dim](env: {active_env})[/dim]...")

    # Validate up front so a bad/missing workflow fails fast (run_dev builds lazily).
    ws = build_workspace_paths()
    try:
        get_workflow_config(resolve_existing_workflow_yaml(ws, name))
    except WorkflowError as e:
        print_error(str(e))
        if e.tip:
            print_hint(e.tip)
        raise Exit(1)

    session = LoomSession(session_id=str(uuid4()), user_id="cli")

    if message:
        print_hint(f"You: [white]{message}[/white]")
        try:
            with console.status("Workflow is running..."):
                run = run_dev(name, message, session, env=active_env, kind="workflow")
            print_success(f"Workflow: [white]{run.response.answer}[/white]")
        except LoomError as e:
            print_error(f"Workflow error: {e}")
            raise Exit(1)
        raise Exit(0)

    print_hint(
        f"Starting interactive session with workflow [white]{name}[/white].\n"
        "Type [bold red]exit[/bold red] or [bold red]quit[/bold red] to stop."
    )
    while True:
        try:
            user_input = Prompt.ask("\n[bold blue]You[/bold blue]")
            if user_input.lower() in ["exit", "quit"]:
                print_hint("Ending session. Bye!")
                break
            if not user_input.strip():
                continue
            with console.status("[bold green]Running...[/bold green]"):
                run = run_dev(name, user_input, session, env=active_env, kind="workflow")
            print_success(f"\n{name}:")
            print_success(run.response.answer)
        except KeyboardInterrupt:
            print_hint("Session interrupted by user. Bye!")
            break
        except LoomError as e:
            print_error(f"Workflow error: {e}")
