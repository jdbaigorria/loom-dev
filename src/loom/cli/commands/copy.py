from typer import Argument, Exit, Typer

from loom.core.exceptions import (
    AgentAlreadyExistsError,
    NoAgentsFoundError,
    ProjectNotInitializedError,
)
from loom.services.agent_service import copy_agent
from loom.utils.ui import print_error, print_success

app: Typer = Typer()


@app.callback(invoke_without_command=True)
def copy_agent_cmd(
    source: str = Argument(..., help="Name of the source agent"),
    dest: str = Argument(..., help="Name of the new agent"),
):
    """Clone an existing agent with a new name."""
    try:
        files = copy_agent(source, dest)
        print_success(
            f"Agent [white]{source}[/white] copied to [white]{dest}[/white] ({len(files)} files)"
        )
    except NoAgentsFoundError as e:
        print_error(str(e))
        raise Exit(1)
    except AgentAlreadyExistsError as e:
        print_error(str(e))
        raise Exit(1)
    except ProjectNotInitializedError as e:
        print_error(str(e))
        raise Exit(1)
    except Exception as e:
        print_error(f"Error copying agent: {e}")
        raise Exit(1)
