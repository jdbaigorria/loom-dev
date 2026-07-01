from typer import Exit, Typer

import loom.utils.ui as ui
from loom.cli.renders.agent_renderer import render_agents_table
from loom.core.exceptions import NoAgentsFoundError, ProjectNotInitializedError
from loom.schemas.config.agent_summary import AgentSummary
from loom.services.agent_service import get_all_agents

app: Typer = Typer()


@app.callback(invoke_without_command=True)
def list_agents():
    try:
        agents: list[AgentSummary] = get_all_agents()
        render_agents_table(agents)

    except ProjectNotInitializedError:
        ui.print_error(
            "The project is not initialized. Please run 'loom init' to initialize the project."
        )
        ui.print_error("Run 'loom init' first.")
        raise Exit(1)

    except NoAgentsFoundError:
        ui.print_error("No agents found in the project.")
        ui.print_error("Create one with 'loom agent new <name>'.")
        raise Exit(0)
