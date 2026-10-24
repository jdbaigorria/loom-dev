import sys
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from loom.core.exceptions import (
    NoAgentsFoundError,
    ProjectAlreadyInitializedError,
    ProjectNotInitializedError,
    ValidationResult,
)
from loom.core.paths import INIT_TEMPLATES, build_workspace_paths, workspace_dir_name
from loom.services.agent_service import get_all_agents, validate_agent
from loom.utils.render import apply_template

# Minimum supported Python version — single source of truth used by run_doctor.
MIN_PYTHON = (3, 11)


def run_doctor(check_aws: bool = True) -> dict[str, list[ValidationResult]]:
    """Validate that the full environment is ready to use LOOM.

    Runs system, AWS (optional), project, and agent checks.

    Args:
        check_aws: If ``True``, verifies AWS credentials and Bedrock access.

    Returns:
        Dict with sections ``"sistema"``, ``"aws"``, ``"proyecto"``,
        and ``"agentes"``, each containing a list of ``ValidationResult``.
    """
    results: dict[str, list[ValidationResult]] = {
        "system": [],
        "aws": [],
        "project": [],
        "agents": [],
        "plugins": [],
    }

    # System
    py_ok = sys.version_info >= MIN_PYTHON
    results["system"].append(
        ValidationResult(
            ok=py_ok,
            message=f"Python {sys.version.split()[0]}",
            tip=f"LOOM requires Python >= {MIN_PYTHON[0]}.{MIN_PYTHON[1]}" if not py_ok else None,
        )
    )
    try:
        loom_version = version("loom")
        results["system"].append(ValidationResult(ok=True, message=f"loom {loom_version}"))
    except PackageNotFoundError:
        results["system"].append(
            ValidationResult(
                ok=False,
                message="loom not installed as a package",
                tip="Run: pip install -e .",
            )
        )

    # AWS
    if check_aws:
        try:
            import boto3

            creds = boto3.Session().get_credentials()
            if creds is None:
                raise ValueError("no credentials")
            creds.get_frozen_credentials()
            results["aws"].append(ValidationResult(ok=True, message="AWS credentials configured"))
        except Exception:
            results["aws"].append(
                ValidationResult(
                    ok=False,
                    message="No AWS credentials",
                    tip="Set AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY or run 'aws configure'",
                )
            )

        try:
            import boto3

            from loom.core.loaders.app import get_app_config

            config = get_app_config(build_workspace_paths().config_file)
            boto3.client("bedrock", region_name=config.region).list_foundation_models(
                byProvider="Anthropic"
            )
            results["aws"].append(
                ValidationResult(
                    ok=True,
                    message=f"Bedrock accessible in {config.region}",
                )
            )
        except Exception as e:
            results["aws"].append(
                ValidationResult(
                    ok=False,
                    message="Bedrock not accessible",
                    tip=str(e),
                )
            )

    # Project
    loom_toml = build_workspace_paths().loom_file
    results["project"].append(
        ValidationResult(
            ok=loom_toml.exists(),
            message="loom.toml found" if loom_toml.exists() else "loom.toml not found",
            tip="Run: loom init" if not loom_toml.exists() else None,
        )
    )

    app_yml = build_workspace_paths().config_file
    try:
        from loom.core.loaders.app import get_app_config

        get_app_config(app_yml)
        results["project"].append(ValidationResult(ok=True, message="app.yml valid"))
    except Exception as e:
        results["project"].append(
            ValidationResult(
                ok=False,
                message="app.yml invalid or not found",
                tip=str(e),
            )
        )

    # Agents — one summary row per agent
    try:
        agents = get_all_agents()
        for agent in agents:
            agent_results = validate_agent(agent.name)
            errors = [r for r in agent_results if not r.ok]
            if not errors:
                results["agents"].append(
                    ValidationResult(
                        ok=True,
                        message=f"{agent.name} — OK",
                    )
                )
            else:
                n = len(errors)
                results["agents"].append(
                    ValidationResult(
                        ok=False,
                        message=f"{agent.name} — {n} error{'s' if n > 1 else ''}",
                        tip=f"Run: loom agent validate {agent.name}",
                    )
                )
    except (ProjectNotInitializedError, NoAgentsFoundError):
        pass  # no project or no agents: empty section, not a doctor error

    from loom.adapters.strands import capabilities
    from loom.cli.plugins import cli_plugin_status

    for name, ok in capabilities.snapshot().items():
        if not name.startswith("agent."):
            continue
        results["system"].append(
            ValidationResult(
                ok=ok,
                message=f"strands accepts {name.removeprefix('agent.')}",
                tip=None
                if ok
                else "The installed strands-agents build does not accept this parameter.",
            )
        )

    for name, dist, dist_version, error in cli_plugin_status():
        label = f"{name} ({dist} {dist_version})"
        if error is None:
            results["plugins"].append(ValidationResult(ok=True, message=label))
        else:
            results["plugins"].append(
                ValidationResult(ok=False, message=label, tip=f"{type(error).__name__}: {error}")
            )

    return results


def _with_workspace_dir(context: dict) -> dict:
    """Inject ``workspace_dir`` so every caller of ``loom init`` uses one name.

    The interactive wizard stores the name under ``app.workspace_name``. A bare
    context (or none) falls back to ``warp``.
    """
    app = context.get("app")
    raw = app.get("workspace_name") if isinstance(app, dict) else None
    if not isinstance(raw, str):
        raw = context.get("workspace_name")
    enriched = dict(context)
    enriched["workspace_dir"] = workspace_dir_name(raw if isinstance(raw, str) else None)
    return enriched


def init_project(context: dict | None = None, force: bool = False) -> list[Path]:
    """Initialize a new Loom project workspace.

    Creates the complete project scaffold by applying the project initialization
    template. This sets up:

    - `loom.toml` - Project configuration file
    - `.loom/` - Metadata directory for stats, sessions, evals
    - `warp/` - Workspace directory (configurable)
    - `warp/agents/` - Agents directory structure
    - `warp/config/` - Configuration directory
    - `warp/hooks/` - Custom hooks directory
    - `warp/evals/` - Evaluation definitions directory
    - Default agent template (if not already present)

    Args:
        context: Template variables for customization (e.g., project_name).
            Common variables:
            - `project_name`: Project name (used in configs)
            - `workspace_name`: Workspace directory name (default: "warp")
            - `description`: Project description
        force: If True, reinitialize even if project already exists.
            If False, raises ProjectAlreadyInitializedError if project initialized.

    Returns:
        list[Path]: Paths of all created files and directories.

    Raises:
        ProjectAlreadyInitializedError: If project already initialized and force=False.
        Exception: If template application fails (permissions, disk space, etc.).

    Example:
        Initialize a new project::

            files = init_project(
                context={
                    "project_name": "quality_checker",
                    "workspace_name": "warp"
                }
            )
            print(f"Created {len(files)} files/directories")
    """
    ws = build_workspace_paths()
    if (ws.loom_file.exists() or ws.metadata_dir.exists()) and not force:
        raise ProjectAlreadyInitializedError()

    try:
        context = _with_workspace_dir(context or {})

        created_files = apply_template(INIT_TEMPLATES, ws.project_root, context)
        ws.metadata_dir.mkdir(parents=True, exist_ok=True)

        return created_files

    except Exception as e:
        raise e
