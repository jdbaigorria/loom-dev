from typer import Exit, Option, Typer

from loom.services.project_service import run_doctor
from loom.utils.ui import print_error

from ..renders.project_renderer import render_doctor

app: Typer = Typer()


@app.callback(invoke_without_command=True)
def doctor(
    no_aws: bool = Option(False, "--no-aws", help="Skip AWS and Bedrock checks"),
):
    """Check that the environment is ready to use LOOM."""
    try:
        sections = run_doctor(check_aws=not no_aws)
        render_doctor(sections)

        has_errors = any(not r.ok for results in sections.values() for r in results)
        if has_errors:
            raise Exit(1)
    except Exit:
        raise
    except Exception as e:
        print_error(f"Error running doctor: {e}")
        raise Exit(1)
