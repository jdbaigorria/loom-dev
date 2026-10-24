"""CLI plugin discovery (entry-point group ``loom.cli``)."""

from typer import Typer
from typer.testing import CliRunner

from loom.cli.plugins import mount_cli_plugins


class _EntryPoint:
    def __init__(self, name: str, load):
        self.name = name
        self._load = load

    def load(self):
        return self._load()


def test_broken_plugin_is_mounted_and_reports_the_error(monkeypatch):
    def _boom():
        raise RuntimeError("missing extra")

    monkeypatch.setattr(
        "loom.cli.plugins.entry_points",
        lambda group: [_EntryPoint("evals", _boom)] if group == "loom.cli" else [],
    )

    app = Typer()
    mount_cli_plugins(app)
    result = CliRunner().invoke(app, ["evals", "run", "agent", "--failures"])

    assert result.exit_code == 1
    assert "could not be loaded" in result.output
    assert "missing extra" in result.output


def test_healthy_plugin_is_mounted(monkeypatch):
    plugin = Typer()

    @plugin.callback(invoke_without_command=True)
    def _hello() -> None:
        print("plugin-ok")

    monkeypatch.setattr(
        "loom.cli.plugins.entry_points",
        lambda group: [_EntryPoint("extra", lambda: plugin)] if group == "loom.cli" else [],
    )

    app = Typer()
    mount_cli_plugins(app)
    result = CliRunner().invoke(app, ["extra"])

    assert result.exit_code == 0
    assert "plugin-ok" in result.output
