"""
loom.services.agent_service — Operaciones CRUD sobre agentes del workspace.

Provee la capa de servicio entre la CLI y el sistema de archivos. Todas las
operaciones usan ``WorkspacePaths`` (vía ``build_workspace_paths()``) y nunca trabajan con paths
hardcodeados.

Funciones públicas:

- ``get_all_agents()`` — lista todos los agentes del workspace.
- ``get_agent_by_name()`` — lee el YAML raw de un agente específico.
- ``delete_agent()`` — elimina el directorio completo de un agente.
- ``create_agent()`` — crea la estructura de archivos de un nuevo agente.
- ``load_agent()`` — carga el agente como instancia Strands ejecutable.
- ``validate_agent()`` — valida la config de un agente sin ejecutarlo.
- ``copy_agent()`` — clona un agente existente con nuevo nombre.
"""

import importlib
import importlib.util
import logging
import re
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Literal
from uuid import uuid4

from loom.adapters.strands import Agent
from loom.core.builder import build_agent
from loom.core.exceptions import (
    AgentAlreadyExistsError,
    AgentInstanceError,
    AgentNotFoundError,
    NoAgentsFoundError,
    ProjectNotInitializedError,
    ValidationResult,
)
from loom.core.paths import AGENT_TEMPLATES, build_workspace_paths
from loom.schemas.config.agent import AgentConfig
from loom.schemas.config.agent_summary import AgentSummary
from loom.schemas.context import LoomSession
from loom.utils.loaders import load_config
from loom.utils.render import apply_template

logger = logging.getLogger(__name__)


def copy_agent(source: str, dest: str) -> list[Path]:
    """Clona un agente existente con nuevo nombre.

    Copia el directorio completo del agente fuente, renombra el YAML de config
    y actualiza el campo ``name:`` dentro del YAML para reflejar el nuevo nombre.

    Args:
        source: Nombre del agente origen.
        dest: Nombre del nuevo agente destino.

    Returns:
        Lista de ``Path`` de todos los archivos del agente clonado.

    Raises:
        NoAgentsFoundError: Si el agente origen no existe.
        AgentAlreadyExistsError: Si el agente destino ya existe.
        ProjectNotInitializedError: Si el workspace no está inicializado.
    """
    ws = build_workspace_paths()
    agents_dir = ws.agents_dir
    if not agents_dir.exists():
        raise ProjectNotInitializedError()

    source_dir = ws.agent_dir(source)
    if not source_dir.exists():
        raise AgentNotFoundError(source)

    dest_dir = ws.agent_dir(dest)
    if dest_dir.exists():
        raise AgentAlreadyExistsError(dest)

    shutil.copytree(source_dir, dest_dir)

    # Rename YAML and update name field:
    old_yaml = dest_dir / "config" / f"{source}.yml"
    new_yaml = dest_dir / "config" / f"{dest}.yml"
    if old_yaml.exists():
        content = old_yaml.read_text(encoding="utf-8")
        content = re.sub(
            r"^name:\s+" + re.escape(source) + r"\s*$",
            f"name: {dest}",
            content,
            count=1,
            flags=re.MULTILINE,
        )
        new_yaml.write_text(content, encoding="utf-8")
        old_yaml.unlink()

    created_files = [p for p in dest_dir.rglob("*") if p.is_file()]
    logger.info("Agent '%s' copied to '%s' (%d files)", source, dest, len(created_files))
    return created_files


def validate_agent(name: str) -> list[ValidationResult]:
    """Validate an agent's configuration without executing it.

    Runs a series of independent checks on the agent config:
    directory, YAML, prompt, tools, and output class.

    Args:
        name: Name of the agent to validate.

    Returns:
        List of ``ValidationResult`` with the outcome of each check.
        If the directory does not exist, returns a single error result
        since further checks cannot proceed.
    """
    ws = build_workspace_paths()
    agent_dir = ws.agent_dir(name)

    if not agent_dir.exists():
        return [
            ValidationResult(
                ok=False,
                message=f"Agent '{name}' not found",
                tip=f"Run: loom agent new {name}",
            )
        ]

    results: list[ValidationResult] = []

    # 1. Valid YAML schema (Pydantic)
    try:
        yaml_path = ws.resolve_agent_yaml(name)
        config = load_config(yaml_path)
        from loom.schemas.config.agent import AgentConfig as _AgentConfig

        agent_config = _AgentConfig(**config)
        results.append(ValidationResult(ok=True, message="YAML schema valid"))
    except Exception as e:
        results.append(ValidationResult(ok=False, message=f"Invalid YAML: {e}"))
        return results  # cannot continue without a valid config

    # 2. Prompt exists on disk (only if source looks like a path, not inline text)
    source = agent_config.system_prompt.prompt
    _unsupported_prefixes = ("s3://", "arn:aws:bedrock:", "http://", "https://")
    if any(source.startswith(p) for p in _unsupported_prefixes):
        results.append(
            ValidationResult(
                ok=False,
                message=f"Prompt uses unsupported source: {source[:30]}...",
                tip="Use a local file (e.g. config/prompt.md) or inline text",
            )
        )
    elif "\n" in source:
        results.append(ValidationResult(ok=True, message="Inline prompt defined"))
    else:
        prompt_path = (agent_dir / "config" / source).resolve()
        exists = prompt_path.is_file() or prompt_path.is_dir()
        results.append(
            ValidationResult(
                ok=exists,
                message="Prompt found" if exists else f"Prompt not found: {source}",
                tip=f"Create the file at {prompt_path}" if not exists else None,
            )
        )

    # 3. Each tool is resolvable — by its own source, not always as a file on disk.
    for tool in agent_config.tools or []:
        if tool.is_builtin:
            # Builtin factories ship with Loom; validate against the registry the
            # runtime resolves them from, not against a (nonexistent) .py file.
            from loom.builtins import BUILTIN_TOOLS

            known = tool.registry_key in BUILTIN_TOOLS
            results.append(
                ValidationResult(
                    ok=known,
                    message=f"Builtin tool '{tool.registry_key}' registered"
                    if known
                    else f"Builtin tool '{tool.registry_key}' unknown",
                    tip=f"Known builtins: {sorted(BUILTIN_TOOLS)}" if not known else None,
                )
            )
        elif tool.source == "import":
            # Dotted import (`module:fn`): resolve the symbol without instantiating
            # or running it — a dry-run that catches a broken reference early.
            from loom.utils.loaders import import_attr

            try:
                import_attr(tool.name)
                results.append(
                    ValidationResult(ok=True, message=f"Import tool '{tool.name}' importable")
                )
            except (ImportError, AttributeError, ValueError) as exc:
                results.append(
                    ValidationResult(
                        ok=False,
                        message=f"Import tool '{tool.name}' not importable",
                        tip=str(exc),
                    )
                )
        else:
            tool_path = (
                ws.shared_tools_dir / f"{tool.name}.py"
                if tool.is_shared
                else agent_dir / "tools" / f"{tool.name}.py"
            )
            results.append(
                ValidationResult(
                    ok=tool_path.exists(),
                    message=f"Tool '{tool.name}' found"
                    if tool_path.exists()
                    else f"Tool '{tool.name}' not found",
                    tip=f"Expected at {tool_path}" if not tool_path.exists() else None,
                )
            )

    # 4. Output class is importable
    if agent_config.output:
        try:
            from loom.core.loaders.output import get_output_class

            get_output_class(agent_config.output, agent_dir)
            results.append(
                ValidationResult(
                    ok=True,
                    message=f"Output class '{agent_config.output}' importable",
                )
            )
        except Exception as e:
            results.append(
                ValidationResult(
                    ok=False,
                    message=f"Output class '{agent_config.output}' not importable",
                    tip=str(e),
                )
            )

    # 5. Each hook exists (built-in, qualified, or local)
    from loom.core.loaders.hook import REGISTRY as _HOOK_REGISTRY

    hooks_dir = ws.hooks_dir
    for hook in agent_config.hooks or []:
        hook_name = hook.name
        if hook_name in _HOOK_REGISTRY:
            results.append(
                ValidationResult(
                    ok=True,
                    message=f"Hook '{hook_name}' (built-in) available",
                )
            )
        elif "." in hook_name:
            try:
                module_path, class_name = hook_name.rsplit(".", 1)
                import importlib as _il

                _mod = _il.import_module(module_path)
                getattr(_mod, class_name)
                results.append(
                    ValidationResult(
                        ok=True,
                        message=f"Hook '{hook_name}' importable",
                    )
                )
            except Exception as e:
                results.append(
                    ValidationResult(
                        ok=False,
                        message=f"Hook '{hook_name}' not importable",
                        tip=str(e),
                    )
                )
        else:
            hook_file = hooks_dir / f"{hook_name}.py"
            results.append(
                ValidationResult(
                    ok=hook_file.exists(),
                    message=f"Hook '{hook_name}' found"
                    if hook_file.exists()
                    else f"Hook '{hook_name}' not found",
                    tip=f"Create the file at {hook_file}" if not hook_file.exists() else None,
                )
            )

    return results


def get_all_agents() -> list[AgentSummary]:
    """List all agents in the workspace with their basic metadata.

    Traverses the subdirectories of ``agents_dir`` and builds an
    ``AgentSummary`` for each one. Agents with invalid or missing YAML
    are included with an error status rather than raising an exception.

    Returns:
        List of ``AgentSummary`` sorted alphabetically by name.

    Raises:
        ProjectNotInitializedError: If ``agents_dir`` does not exist (the project
            has not been initialised with ``loom init``).
        NoAgentsFoundError: If the directory exists but contains no agents.
    """
    ws = build_workspace_paths()
    agent_dirs: Path = ws.agents_dir

    if not agent_dirs.exists() or not agent_dirs.is_dir():
        raise ProjectNotInitializedError()

    agent_folders = [
        f
        for f in agent_dirs.iterdir()
        if f.is_dir() and f.name != "tools" and not f.name.startswith("__")
    ]

    if not agent_folders:
        raise NoAgentsFoundError(
            "No agents found in the project. Please create an agent using 'loom agent new <name>'."
        )

    logger.debug("Found %d agent folder(s) in '%s'", len(agent_folders), agent_dirs)

    agents_list: list[AgentSummary] = []
    for agent_dir in sorted(agent_folders):
        try:
            agent_yaml_path = ws.resolve_agent_yaml(agent_dir.name)
            config = load_config(agent_yaml_path)
            agents_list.append(
                AgentSummary(
                    name=config.get("name", agent_dir.name),
                    description=config.get("description", "N/A"),
                    model=_model_descriptor(config.get("model", "default")),
                    filename=agent_yaml_path.name,
                    status="ok",
                )
            )
        except AgentNotFoundError:
            logger.warning("Agent '%s' has no YAML config file", agent_dir.name)
            agents_list.append(
                AgentSummary(
                    name=agent_dir.name,
                    status="missing",
                    filename=f"No {agent_dir.name}.yml found",
                )
            )
        except Exception as e:
            logger.warning("Agent '%s' has invalid config: %s", agent_dir.name, e)
            agents_list.append(
                AgentSummary(
                    name=agent_dir.name,
                    status="error",
                    error_msg=str(e),
                    filename=f"Invalid YAML: {e}",
                )
            )

    return agents_list


def _model_descriptor(model: object) -> str:
    """Human-readable model for the listing: a profile name or an inline model id."""
    if isinstance(model, str):
        return model  # profile name, e.g. "default"
    if isinstance(model, list):
        return "fallback"
    if isinstance(model, dict):
        if "fallback" in model:
            return "fallback"
        if "route" in model:
            return "classifier"
        params = model.get("params") or {}
        return str(params.get("model_id") or model.get("import_path", "inline"))
    return "default"


def get_agent_by_name(name: str) -> tuple[str, Path]:
    """Lee el contenido YAML raw de un agente y retorna su path.

    Args:
        name: Nombre del agente a buscar.

    Returns:
        Tupla ``(content, path)`` donde ``content`` es el YAML como string
        y ``path`` es el ``Path`` absoluto al archivo.

    Raises:
        NoAgentsFoundError: Si el directorio del agente no existe.
        AgentNotFoundError: Si el directorio existe pero no tiene YAML de config.
    """
    ws = build_workspace_paths()
    agent_dir = ws.agent_dir(name)

    if not agent_dir.exists() or not agent_dir.is_dir():
        raise NoAgentsFoundError(f"Agent {name} not found")

    agent_yaml_path = ws.resolve_agent_yaml(name)
    content = agent_yaml_path.read_text(encoding="utf-8")
    logger.debug("Agent '%s' config read from '%s'", name, agent_yaml_path)
    return (content, agent_yaml_path)


def delete_agent(name: str) -> None:
    """Elimina el directorio completo de un agente.

    Args:
        name: Nombre del agente a eliminar.

    Raises:
        NoAgentsFoundError: Si el agente no existe en el workspace.
    """
    ws = build_workspace_paths()
    agent_dir = ws.agent_dir(name)

    if not agent_dir.exists() or not agent_dir.is_dir():
        raise NoAgentsFoundError(f"Agent {name} not found")

    shutil.rmtree(agent_dir)
    logger.info("Agent '%s' deleted from '%s'", name, agent_dir)


def create_agent(name: str, agent_config: AgentConfig) -> list[Path]:
    """Crea la estructura de archivos de un nuevo agente a partir de templates.

    Genera el directorio ``warp/agents/{name}/`` con el YAML de config,
    el system prompt y los archivos base usando el sistema de templates Jinja2.

    Args:
        name: Nombre del nuevo agente.
        agent_config: Configuración validada del agente (del wizard o del test).

    Returns:
        Lista de ``Path`` de los archivos creados.

    Raises:
        ProjectNotInitializedError: Si el workspace no está inicializado.
        AgentAlreadyExistsError: Si ya existe un agente con ese nombre.
    """
    ws = build_workspace_paths()
    agents_dir = ws.agents_dir

    if not agents_dir.exists() or not agents_dir.is_dir():
        raise ProjectNotInitializedError()

    agent_dir = ws.agent_dir(name)

    if agent_dir.exists() and agent_dir.is_dir():
        raise AgentAlreadyExistsError(name)

    context = {
        "agent": agent_config.model_dump(),
        "folder_name": agent_dir.name,
        "prompt": agent_config.system_prompt.prompt,
    }

    created_files = apply_template(AGENT_TEMPLATES, agent_dir, context)
    logger.info("Agent '%s' created with %d file(s)", name, len(created_files))
    return created_files


@dataclass
class LoadedAgent:
    """Agente cargado listo para ejecutarse.

    Attributes:
        instance: Instancia del agente (``strands.Agent`` o ``AgentConfig``
            dependiendo de la fuente).
        source: Origen de la carga — ``"python"`` si se cargó desde
            ``agent.py``, ``"yaml"`` si se cargó desde el YAML de config.
    """

    instance: Agent
    source: Literal["python", "yaml"]


def load_agent(name: str, session: LoomSession | None = None) -> LoadedAgent:
    """Carga un agente como instancia ejecutable.

    Intenta cargar desde ``agent.py`` (Python nativo) primero. Si no existe,
    carga desde el YAML de config usando ``get_agent_config()``.

    El directorio raíz del proyecto se agrega temporalmente a ``sys.path``
    durante la importación del módulo Python y se remueve al finalizar.

    Args:
        name: Nombre del agente a cargar.

    Returns:
        ``LoadedAgent`` con la instancia y el origen de la carga.

    Raises:
        AgentNotFoundError: Si no existe ni ``agent.py`` ni el YAML de config.
        AgentInstanceError: Si ``agent.py`` existe pero no define una variable
            ``agent`` en el módulo.
    """
    ws = build_workspace_paths()
    agent_dir = ws.agent_dir(name)
    agent_py = agent_dir / "agent.py"

    if agent_py.exists():
        logger.debug("Loading agent '%s' from Python module '%s'", name, agent_py)
        root_str = str(ws.project_root)
        sys.path.insert(0, root_str)
        try:
            spec = importlib.util.spec_from_file_location("agent_module", agent_py)
            if spec is None or spec.loader is None:
                raise ImportError(f"Cannot build module spec from '{agent_py}'")
            agent_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(agent_module)

            agent_instance = getattr(agent_module, "agent", None)
            if not agent_instance:
                raise AgentInstanceError(name)

            logger.info("Agent '%s' loaded from Python module", name)
            return LoadedAgent(instance=agent_instance, source="python")
        finally:
            if root_str in sys.path:
                sys.path.remove(root_str)
    else:
        logger.debug("Loading agent '%s' from YAML config", name)
        ws.resolve_agent_yaml(agent_dir.name)  # raises AgentNotFoundError early if missing
        active_session = session or LoomSession(user_id="cli", session_id=str(uuid4()))
        agent_instance = build_agent(name, active_session)
        logger.info("Agent '%s' loaded from YAML config", name)
        return LoadedAgent(instance=agent_instance, source="yaml")
