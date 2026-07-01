from typer import Argument, Exit, Typer

from loom.core.exceptions import AgentConfigError, NoAgentsFoundError
from loom.services.agent_service import get_agent_by_name
from loom.utils.ui import print_error

from ..renders.agent_renderer import render_agent_yaml

app: Typer = Typer()


@app.callback(invoke_without_command=True)
def view_agent(
    name: str = Argument(..., help="Name of the agent to view"),
):

    try:
        content, path = get_agent_by_name(name)
        render_agent_yaml(content, path, name)
    except NoAgentsFoundError:
        print_error(
            f"Agent [bold]{name}[/bold] does not exist.", tip="Please check the agent name."
        )
        raise Exit(1)

    except AgentConfigError:
        print_error(
            f"Could not find a configuration file for {name}.",
            tip="Please check the agent configuration file.",
        )
        raise Exit(1)

    except Exception as e:
        print_error(
            f"Error reading configuration: {e}", tip="Please check the agent configuration file."
        )
        raise Exit(1)
