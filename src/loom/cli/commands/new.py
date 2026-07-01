from typer import Argument, Exit, Option, Typer

from loom.core.exceptions import AgentAlreadyExistsError, ProjectNotInitializedError
from loom.core.paths import build_workspace_paths
from loom.schemas.config.agent import AgentConfig
from loom.services.agent_service import create_agent
from loom.utils.ui import print_error, print_hint, print_success

from ..renders.agent_renderer import show_preview_agent

app: Typer = Typer()


@app.callback(invoke_without_command=True)
def new_agent(
    name: str = Argument(None, help="Name of the new agent"),
    interactive: bool = Option(False, "--interactive", "-i", help="Run the interactive wizard"),
):

    if interactive:
        from loom.cli.commands.wizard.agent_new import agent_context

        agent_config = agent_context(name)
        name = agent_config.name
    else:
        if not name:
            print_error("You must provide a name or use [bold cyan]--interactive[/bold cyan].")
            print_error("Usage: [bold]loom agent new my_cool_agent[/bold]")
            raise Exit(1)

        print_hint("Using default agent settings...")
        agent_config = AgentConfig(name=name)

    try:
        print_success(f"Weaving agent [white]{name}[/white]...")

        created_files = create_agent(name, agent_config)

        show_preview_agent(
            created_files,
            f"Agent '{name}' Generated Files",
            build_workspace_paths().agent_dir(name),
        )

    except ProjectNotInitializedError as e:
        print_error(f"Error creating agent: {e}")
        print_error("Please run [bold cyan]loom init[/bold cyan] first to set up the project.")
        raise Exit(1)
    except AgentAlreadyExistsError as e:
        print_error(f"Error creating agent: {e}")
        print_error("The agent already exists. Please use a different name.")
        raise Exit(1)
    except Exception as e:
        print_error(f"Error creating agent: {e}")
        raise Exit(1)
