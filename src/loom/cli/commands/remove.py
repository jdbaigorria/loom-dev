from typer import Argument, Exit, Option, Typer, confirm

from loom.core.exceptions import NoAgentsFoundError
from loom.services.agent_service import delete_agent
from loom.utils.ui import print_error, print_success, print_warning

app: Typer = Typer()


@app.callback(invoke_without_command=True)
def remove_agent(
    name: str = Argument(..., help="Name of the agent to remove"),
    force: bool = Option(False, "--force", "-f", help="Force removal without confirmation"),
):

    if not force:
        sure = confirm(f"Are you sure you want to delete the agent '{name}' and ALL its files?")
        if not sure:
            print_warning("Operation cancelled. Your agent is safe.")
            raise Exit(0)

    try:
        delete_agent(name)
        print_success(f"Agent {name} removed successfully!")
    except NoAgentsFoundError:
        print_error(f"Agent {name} not found.", tip="Please check the agent name.")
        raise Exit(1)

    except Exception as e:
        print_error(f"Error removing agent: {e}")
        raise Exit(1)
