"""
loom.services.evals_service — Operaciones de evaluación de agentes.

Provee la capa de servicio entre la CLI y LoomEvals. Todas las operaciones
lanzan excepciones tipadas de ``loom.core.exceptions`` para que el command
las capture y las muestre de forma consistente.

Funciones públicas:

- ``new_evals()`` — genera el archivo evals.yml de un agente desde template.
- ``run_evals()`` — ejecuta las evaluaciones de un agente y retorna los reports.
- ``get_history()`` — retorna el historial de runs de un agente.
- ``check_regression()`` — compara los últimos dos runs y detecta regresiones.
- ``get_failed_cases()`` — extrae los casos fallidos del último run o de reports dados.
"""

import logging
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from loom.core.exceptions import (
    AgentNotFoundError,
    EvalsAlreadyExistsError,
    EvalsNotFoundError,
    EvalsRunError,
)
from loom.core.paths import EVALS_TEMPLATES, build_workspace_paths
from loom.loom_evals import LoomEvals

logger = logging.getLogger(__name__)


def new_evals(name: str) -> Path:
    """Genera el archivo evals.yml para un agente desde template.

    Args:
        name: Nombre del agente.

    Returns:
        Path al archivo evals.yml creado.

    Raises:
        AgentNotFoundError: Si el directorio del agente no existe.
        EvalsAlreadyExistsError: Si ya existe un evals.yml para el agente.
    """
    ws = build_workspace_paths()
    if not ws.agent_dir(name).exists():
        raise AgentNotFoundError(name)

    eval_file = ws.eval_file(name)
    if eval_file.exists():
        raise EvalsAlreadyExistsError(name)

    env = Environment(
        loader=FileSystemLoader(EVALS_TEMPLATES), trim_blocks=True, lstrip_blocks=True
    )
    content = env.get_template("evals.yml.j2").render(name=name)

    eval_file.parent.mkdir(parents=True, exist_ok=True)
    eval_file.write_text(content, encoding="utf-8")

    logger.info("Evals file created for agent '%s' at %s", name, eval_file)
    return eval_file


def run_evals(name: str) -> list:
    """Ejecuta las evaluaciones de un agente y retorna los reports.

    Args:
        name: Nombre del agente a evaluar.

    Returns:
        Lista de ``EvaluationReport`` con los resultados por evaluador.

    Raises:
        EvalsNotFoundError: Si no existe el archivo evals.yml para el agente.
        EvalsRunError: Si la ejecución de las evaluaciones falla.
    """
    _assert_evals_exist(name)
    try:
        return LoomEvals(name).run()
    except Exception as e:
        logger.error("Evals run failed for agent '%s': %s", name, str(e))
        raise EvalsRunError(str(e))


def get_history(name: str) -> list[dict]:
    """Return the full history of evaluation runs.

    Args:
        name: Agent name.

    Returns:
        List of historical records. Empty if there are no previous runs.

    Raises:
        EvalsNotFoundError: If the evals directory for the agent does not exist.
    """
    _assert_evals_exist(name)
    return LoomEvals(name).history()


def check_regression(name: str, threshold: float = 0.05) -> dict:
    """Compare the last two runs and detect score regressions.

    Args:
        name: Agent name.
        threshold: Maximum allowed score drop before marking a regression.

    Returns:
        Dict with ``status`` and ``regressions``. See ``LoomEvals.check_regression``.

    Raises:
        EvalsNotFoundError: If the evals directory for the agent does not exist.
    """
    _assert_evals_exist(name)
    return LoomEvals(name).check_regression(threshold=threshold)


def get_failed_cases(name: str, reports: list | None = None) -> list[dict]:
    """Extract failed cases from the last run or from the provided reports.

    Args:
        name: Agent name.
        reports: Reports from a recent run. If None, uses the last run from history.

    Returns:
        List of dicts with cases that did not pass. See ``LoomEvals.failed_cases``.

    Raises:
        EvalsNotFoundError: If the evals directory for the agent does not exist.
    """
    _assert_evals_exist(name)
    return LoomEvals(name).failed_cases(reports)


# ------------------------------------------------------------------
# Internal helpers
# ------------------------------------------------------------------


def _assert_evals_exist(name: str) -> None:
    """Lanza EvalsNotFoundError si no existe el archivo evals.yml del agente."""
    if not build_workspace_paths().eval_file(name).exists():
        raise EvalsNotFoundError(name)
