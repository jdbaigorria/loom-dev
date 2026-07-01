from typer import Argument, Exit, Typer

from loom.services.agent_service import validate_agent
from loom.utils.ui import print_error

from ..renders.agent_renderer import render_agent_validation

app: Typer = Typer()


@app.callback(invoke_without_command=True)
def agent_validate(
    name: str = Argument(..., help="Name of the agent to validate"),
):
    """Validate agent configuration without running it."""
    try:
        results = validate_agent(name)
        render_agent_validation(name, results)

        if not all(r.ok for r in results):
            raise Exit(1)
    except Exit:
        raise
    except Exception as e:
        print_error(f"Error validating agent: {e}")
        raise Exit(1)
