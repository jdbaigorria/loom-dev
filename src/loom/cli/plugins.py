"""Discovery of optional ``loom`` CLI plugins (entry-point group ``loom.cli``)."""

from importlib.metadata import PackageNotFoundError, entry_points, version

from typer import Exit, Typer

from loom.utils.ui import print_error, print_hint


def _mount_broken_plugin(app: Typer, name: str, exc: BaseException) -> None:
    """Mount ``name`` as a command that reports why the plugin failed to load.

    A plain command (not a group) that swallows every argument, so ``loom evals``,
    ``loom evals run x --failures`` and ``loom evals --help`` all show the real cause.
    """

    @app.command(
        name=name,
        help=f"(unavailable) the '{name}' plugin failed to load",
        context_settings={
            "allow_extra_args": True,
            "ignore_unknown_options": True,
            "help_option_names": [],
        },
    )
    def _report() -> None:
        print_error(f"The '{name}' plugin could not be loaded: {exc}")
        print_hint("Run `loom doctor` for details, or reinstall the plugin package.")
        raise Exit(1)


def mount_cli_plugins(app: Typer) -> None:
    """Mount every ``loom.cli`` entry point. A plugin that fails to load is still mounted."""
    for ep in entry_points(group="loom.cli"):
        try:
            app.add_typer(ep.load(), name=ep.name)
        except Exception as exc:  # any load failure, including LoomStrandsCompatError
            _mount_broken_plugin(app, ep.name, exc)


def cli_plugin_status() -> list[tuple[str, str, str, BaseException | None]]:
    """Return ``(name, distribution, version, error)`` for each installed CLI plugin."""
    rows: list[tuple[str, str, str, BaseException | None]] = []
    for ep in entry_points(group="loom.cli"):
        dist = ep.dist.name if ep.dist is not None else "unknown"
        try:
            dist_version = version(dist)
        except PackageNotFoundError:
            dist_version = "unknown"
        error: BaseException | None
        try:
            ep.load()
            error = None
        except Exception as exc:
            error = exc
        rows.append((ep.name, dist, dist_version, error))
    return rows
