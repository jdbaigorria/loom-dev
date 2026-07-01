from typer import Exit, Option, Typer

from loom.config.defaults import DEFAULT_REGION
from loom.core.exceptions import ProjectAlreadyInitializedError
from loom.core.paths import build_workspace_paths
from loom.schemas.config.app import AppConfig
from loom.services.project_service import init_project
from loom.utils.ui import print_error, print_hint, print_success, print_warning

from ..renders.project_renderer import show_preview_project

app: Typer = Typer()


@app.callback(invoke_without_command=True)
def init(
    region: str = Option(
        DEFAULT_REGION, "--region", "-r", help="The region to use for the project"
    ),
    force: bool = Option(False, "--force", "-f", help="Force the project to be generated"),
    interactive: bool = Option(False, "--interactive", "-i", help="Interactive mode"),
):

    if interactive:
        from loom.cli.commands.wizard.app_init import app_context

        init_ctx = app_context(region)
        context = init_ctx.to_template_context()
    else:
        app_config = AppConfig(region=region)
        context = {"app": app_config.model_dump(exclude_none=True)}

    try:
        ws = build_workspace_paths()
        print_success(f"Initializing project in {ws.project_root}")

        created_files = init_project(context, force=force)

        show_preview_project(created_files, "Project Generated Files", ws.project_root)

    except ProjectAlreadyInitializedError:
        print_warning("A LOOM project already exists in this directory.")
        print_hint("Use the [bold cyan]--force[/] flag to overwrite.")
        raise Exit(1)

    except Exception as e:
        print_error(f"Error during initialization: {e}")
        raise Exit(1)
