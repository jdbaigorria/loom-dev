"""``loom agent dev`` — interactive REPL that hot-reloads on file edits.

Like ``loom agent run`` (interactive), but before each turn it fingerprints the
agent's config, prompts, and tools (and the shared/app dirs) by modification
time; when anything changed, it clears the on-disk caches and rebuilds the agent
so the next message uses the edited definition — no restart. A reload that fails
to validate keeps the previous working agent and prints the error.
"""

from pathlib import Path
from uuid import uuid4

from rich.prompt import Prompt
from typer import Argument, Exit, Option, Typer

from loom.cli.commands.run import resolve_control
from loom.core.exceptions import AgentConfigError, AgentNotFoundError
from loom.core.loaders.app import resolve_env
from loom.core.paths import build_workspace_paths
from loom.core.reload import clear_config_caches
from loom.dev import build_dev_agent, run_turn
from loom.schemas.context import LoomSession
from loom.utils.ui import console, print_error, print_hint, print_success

app: Typer = Typer()

_WATCH_EXT = {".yml", ".yaml", ".md", ".txt", ".py"}


def _fingerprint(paths: list[Path]) -> dict[str, float]:
    """Map watched file → mtime across the given dirs (recursive)."""
    fingerprint: dict[str, float] = {}
    for base in paths:
        if not base.is_dir():
            continue
        for file in base.rglob("*"):
            if file.is_file() and file.suffix in _WATCH_EXT:
                try:
                    fingerprint[str(file)] = file.stat().st_mtime
                except OSError:
                    continue
    return fingerprint


@app.callback(invoke_without_command=True)
def dev_agent(
    name: str = Argument(..., help="Name of the agent to run in dev mode"),
    env: str = Option(None, "--env", "-e", help="Environment profile. Overrides LOOM_ENV"),
) -> None:
    """Run an agent in a hot-reloading interactive session."""
    active_env = env or resolve_env()
    ws = build_workspace_paths()
    watched = [ws.agent_dir(name), ws.shared_tools_dir, ws.app_dir]

    print_hint(f"Dev mode for [white]{name}[/white] [dim](env: {active_env})[/dim]...")

    session = LoomSession(session_id=str(uuid4()), user_id="cli")
    try:
        clear_config_caches()
        dev = build_dev_agent(name, session, env=active_env)
    except AgentNotFoundError as e:
        print_error(str(e))
        raise Exit(1)
    except AgentConfigError as e:
        print_error(f"Invalid agent config: {e}")
        raise Exit(1)

    fingerprint = _fingerprint(watched)

    print_hint(
        "Edits to config, prompts, and tools reload automatically before the next message.\n"
        "Type [bold red]exit[/bold red] or [bold red]quit[/bold red] to stop."
    )

    def _teardown_mcp() -> None:
        dev.agent.cleanup()

    while True:
        try:
            user_input = Prompt.ask("\n[bold blue]You[/bold blue]")
            if user_input.lower() in ["exit", "quit"]:
                print_hint("Ending dev session. Bye!")
                break
            if not user_input.strip():
                continue

            current = _fingerprint(watched)
            if current != fingerprint:
                fingerprint = current
                try:
                    _teardown_mcp()
                    clear_config_caches()
                    dev = build_dev_agent(name, session, env=active_env)
                    print_hint("↻ reloaded")
                except Exception as e:
                    print_error(f"Reload failed (keeping previous version): {e}")

            with console.status("[bold green]Thinking...[/bold green]"):
                response, _ = run_turn(dev, user_input, session)
            response = resolve_control(dev, session, response)

            print_success(f"\n{name}:")
            print_success(response.answer)

        except KeyboardInterrupt:
            print_hint("Session interrupted by user. Bye!")
            break
        except Exception as e:
            print_error(f"Agent error: {e}")

    _teardown_mcp()
