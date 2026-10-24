"""Rendering helpers for evaluation CLI output."""

from rich.panel import Panel
from rich.table import Table

from loom.utils.ui import console


def render_evals_results(name: str, reports: list) -> None:
    """Display evaluation results in a Rich table panel."""
    console.print()
    console.print(
        Panel(
            _build_results_table(reports),
            title=f"[bold magenta]🧪 Evals: [white]{name}[/white][/bold magenta]",
            border_style="magenta",
            expand=False,
        )
    )
    console.print()


def render_evals_regression(result: dict) -> None:
    """Display regression analysis between the last two runs."""
    status = result["status"]

    if status == "no_history":
        console.print("[warning]![/warning] No run history found.")
    elif status == "single_run":
        console.print("[warning]![/warning] Only one run found — nothing to compare against.")
    elif status == "regression":
        console.print("[error]⚠  Regresiones detectadas:[/error]")
        for ev, data in result["regressions"].items():
            console.print(
                f"  [white]{ev}[/white]: "
                f"[dim]{data['previous']:.2f}[/dim] → "
                f"[red]{data['current']:.2f}[/red] "
                f"([red]{data['delta']:+.2f}[/red])"
            )
    else:
        console.print("[success]✔[/success] Sin regresiones.")


def render_evals_failures(failures: list) -> None:
    """Display failed cases with their input, expected output, and actual output."""
    if not failures:
        console.print("[success]✔[/success] All cases passed.")
        return

    for f in failures:
        actual = (f["actual"] or "")[:100]
        reason = (f["reason"] or "")[:100]
        console.print(
            f"\n[red]✗[/red] [[cyan]{f['evaluator']}[/cyan]] [white]{f['case']}[/white] ([dim]{f['score']:.2f}[/dim])"
        )
        console.print(f"  [dim]Input:[/dim]    {f['input']}")
        console.print(f"  [dim]Expected:[/dim] {f['expected']}")
        console.print(f"  [dim]Actual:[/dim]   {actual}...")
        console.print(f"  [dim]Reason:[/dim]   {reason}...")


def render_evals_compare(records: list) -> None:
    """Display run history grouped by timestamp."""
    if not records:
        console.print("[warning]![/warning] No saved runs found.")
        return

    runs: dict[str, list] = {}
    for r in records:
        runs.setdefault(r["run_ts"], []).append(r)

    for ts, entries in runs.items():
        console.print(f"\n  [dim]Run:[/dim] [white]{ts}[/white]")
        for entry in entries:
            score = entry["overall_score"]
            evaluator = entry.get("evaluator_name", "unknown")
            bar = "[green]█[/green]" * int(score * 20) + "[dim]░[/dim]" * (20 - int(score * 20))
            console.print(f"    [cyan]{evaluator:<30}[/cyan] {bar} [white]{score:.2f}[/white]")


def _build_results_table(reports: list) -> Table:
    """Build a Rich grid table from a list of evaluator reports."""
    table = Table.grid(padding=(0, 1))
    table.add_column(width=2)
    table.add_column(min_width=15)
    table.add_column(width=6, justify="right")
    table.add_column(ratio=1)

    for item in reports:
        if isinstance(item, tuple) and len(item) == 2 and isinstance(item[0], str):
            name, report = item
        else:
            name, report = getattr(item, "evaluator_name", "unknown"), item
        score = report.overall_score
        passed = sum(report.test_passes)
        total = len(report.test_passes)
        color = "green" if score >= 0.8 else "yellow" if score >= 0.5 else "red"

        table.add_row(
            "",
            f"[{color} bold]{name}[/]",
            f"[{color}]{score:.2f}[/]",
            f"[dim]({passed}/{total} passed)[/dim]",
        )

        for i, case in enumerate(report.cases):
            status = "[green]✓[/]" if report.test_passes[i] else "[red]✗[/]"
            name = case.get("name", f"case-{i}")
            case_score = report.scores[i]
            reason = report.reasons[i] if i < len(report.reasons) else ""
            case_color = "green" if case_score >= 0.8 else "yellow" if case_score >= 0.5 else "red"

            table.add_row(
                status,
                f"[dim]  {name}[/dim]",
                f"[{case_color}]{case_score:.2f}[/]",
                f"[dim]{reason}[/dim]",
            )

    return table
