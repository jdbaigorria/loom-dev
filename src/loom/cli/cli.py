from typer import Typer

from .commands.copy import app as copy_agent_app
from .commands.dev import app as dev_agent_app
from .commands.doctor import app as doctor_app
from .commands.edit import app as edit_agent_app
from .commands.init import app as init_app
from .commands.list import app as list_agents_app
from .commands.new import app as new_agent
from .commands.remove import app as remove_agent_app
from .commands.run import app as run_agent_app
from .commands.stats import app as stats_agent_app
from .commands.validate import app as validate_agent_app
from .commands.version import app as version_app
from .commands.view import app as view_agent_app
from .commands.workflow import app as workflow_app
from .plugins import mount_cli_plugins

app = Typer(
    name="loom",
    help="🧵 LOOM — Declarative AI Agent Framework",
    no_args_is_help=True,
)

# Commands for agents
agent_app = Typer(help="Manage agents")
agent_app.add_typer(new_agent, name="new")
agent_app.add_typer(list_agents_app, name="list")
agent_app.add_typer(remove_agent_app, name="remove")
agent_app.add_typer(view_agent_app, name="view")
agent_app.add_typer(run_agent_app, name="run")
agent_app.add_typer(dev_agent_app, name="dev")
agent_app.add_typer(stats_agent_app, name="stats")
agent_app.add_typer(validate_agent_app, name="validate")
agent_app.add_typer(copy_agent_app, name="copy")
agent_app.add_typer(edit_agent_app, name="edit")

# Add commands to the main app
app.add_typer(init_app, name="init")
app.add_typer(agent_app, name="agent")
app.add_typer(doctor_app, name="doctor")
app.add_typer(version_app, name="version")
app.add_typer(workflow_app, name="workflow")

# Optional CLI plugins (group ``loom.cli``). A plugin that fails to load is still
# mounted, as a command that reports the error — never silently dropped.
mount_cli_plugins(app)

# `loom evals` still ships inside this package until it moves to loom-declarative-evals.
# Register it only when that stack is importable, so a `[cli]`-only install keeps working.
try:
    from .commands.evals import app as evals_app
except ImportError:
    pass
else:
    app.add_typer(evals_app, name="evals")

if __name__ == "__main__":
    app()
