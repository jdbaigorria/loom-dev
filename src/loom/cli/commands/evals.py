from typer import Argument, Exit, Option, Typer

from loom.core.exceptions import (
    AgentNotFoundError,
    EvalsAlreadyExistsError,
    EvalsNotFoundError,
    EvalsRunError,
)
from loom.services.evals_service import (
    check_regression,
    get_failed_cases,
    get_history,
    new_evals,
    run_evals,
)
from loom.utils.ui import console, print_error, print_hint, print_success, print_warning

from ..renders.evals_renderer import (
    render_evals_compare,
    render_evals_failures,
    render_evals_regression,
    render_evals_results,
)

app: Typer = Typer()


@app.command("new")
def evals_new(
    name: str = Argument(..., help="Name of the agent to create evals for"),
):
    """Generate a starter evals.yml for an agent."""
    try:
        eval_file = new_evals(name)
        print_success(f"Evals file created for [white]{name}[/white].")
        print_hint(
            f"Edit the file at [dim]{eval_file}[/dim] and run [bold]loom evals run {name}[/bold]."
        )
    except AgentNotFoundError as e:
        print_error(str(e), tip=e.tip)
        raise Exit(1)
    except EvalsAlreadyExistsError as e:
        print_error(str(e), tip=e.tip)
        raise Exit(1)


@app.command("run")
def evals_run(
    name: str = Argument(..., help="Name of the agent to evaluate"),
    regression: bool = Option(False, "--regression", "-r", help="Check regression after run"),
    failures: bool = Option(False, "--failures", "-f", help="Show failed cases after run"),
):
    """Run evaluations for an agent and display results."""
    try:
        with console.status(f"Running evals for [white]{name}[/white]..."):
            reports = run_evals(name)
        render_evals_results(name, reports)

        if regression:
            result = check_regression(name)
            render_evals_regression(result)

        if failures:
            failed = get_failed_cases(name, reports)
            render_evals_failures(failed)

    except EvalsNotFoundError as e:
        print_error(str(e), tip=e.tip)
        raise Exit(1)
    except EvalsRunError as e:
        print_error(str(e))
        raise Exit(1)


@app.command("compare")
def evals_compare(
    name: str = Argument(..., help="Name of the agent"),
):
    """Show evaluation history grouped by run."""
    try:
        records = get_history(name)
    except EvalsNotFoundError as e:
        print_error(str(e), tip=e.tip)
        raise Exit(1)

    if not records:
        print_warning(f"No eval history found for [bold]{name}[/bold].")
        raise Exit(0)

    render_evals_compare(records)


@app.command("failures")
def evals_failures(
    name: str = Argument(..., help="Name of the agent"),
):
    """Show failed cases from the last evaluation run."""
    try:
        failed = get_failed_cases(name)
    except EvalsNotFoundError as e:
        print_error(str(e), tip=e.tip)
        raise Exit(1)

    render_evals_failures(failed)


@app.command("regression")
def evals_regression(
    name: str = Argument(..., help="Name of the agent"),
    threshold: float = Option(
        0.05, "--threshold", "-t", help="Allowed score decrease before flagging regression"
    ),
):
    """Check for performance regressions between last two eval runs."""
    try:
        result = check_regression(name, threshold=threshold)
    except EvalsNotFoundError as e:
        print_error(str(e), tip=e.tip)
        raise Exit(1)

    render_evals_regression(result)
