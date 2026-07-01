"""
tests/unit/test_evals_service.py

Cubre loom.services.evals_service:
  - run_evals()
  - get_history()
  - check_regression()
  - get_failed_cases()

Los tests mockean ``build_workspace_paths().eval_file`` y LoomEvals para aislar el servicio.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

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

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_eval_file(exists: bool):
    """Retorna un mock de Path con .exists() configurado."""
    m = MagicMock(spec=Path)
    m.exists.return_value = exists
    return m


def _mock_workspace_paths(exists: bool):
    """Mock de workspace con ``eval_file`` que retorna el stub."""
    m = MagicMock()
    m.eval_file.return_value = _mock_eval_file(exists)
    return m


# ---------------------------------------------------------------------------
# new_evals() — EVL-SVC-N01 a EVL-SVC-N04
# ---------------------------------------------------------------------------


class TestNewEvals:
    def _mock_workspace(self, agent_exists: bool, evals_exists: bool, tmp_path):
        m = MagicMock()
        agent_dir = tmp_path / "my_agent" if agent_exists else tmp_path / "nonexistent"
        if agent_exists:
            agent_dir.mkdir(parents=True)
        m.agent_dir.return_value = agent_dir
        eval_file = tmp_path / "my_agent" / "evals" / "evals.yml"
        if evals_exists:
            eval_file.parent.mkdir(parents=True, exist_ok=True)
            eval_file.write_text("exists")
        m.eval_file.return_value = eval_file
        return m

    def test_agente_no_existe_lanza_agent_not_found(self, tmp_path):
        """EVL-SVC-N01: agent_dir no existe → AgentNotFoundError"""
        mock_p = self._mock_workspace(agent_exists=False, evals_exists=False, tmp_path=tmp_path)
        with patch("loom.services.evals_service.build_workspace_paths", return_value=mock_p):
            with pytest.raises(AgentNotFoundError):
                new_evals("my_agent")

    def test_evals_yml_ya_existe_lanza_evals_already_exists(self, tmp_path):
        """EVL-SVC-N02: evals.yml ya existe → EvalsAlreadyExistsError"""
        mock_p = self._mock_workspace(agent_exists=True, evals_exists=True, tmp_path=tmp_path)
        with patch("loom.services.evals_service.build_workspace_paths", return_value=mock_p):
            with pytest.raises(EvalsAlreadyExistsError) as exc_info:
                new_evals("my_agent")
        assert "my_agent" in str(exc_info.value)

    def test_crea_evals_yml_con_nombre_del_agente(self, tmp_path):
        """EVL-SVC-N03: agente existe y sin evals.yml → crea el archivo con el nombre del agente"""
        mock_p = self._mock_workspace(agent_exists=True, evals_exists=False, tmp_path=tmp_path)
        with patch("loom.services.evals_service.build_workspace_paths", return_value=mock_p):
            result = new_evals("my_agent")

        assert result.exists()
        content = result.read_text()
        assert "my_agent" in content

    def test_retorna_path_del_archivo_creado(self, tmp_path):
        """EVL-SVC-N04: new_evals exitoso → retorna Path al evals.yml creado"""
        mock_p = self._mock_workspace(agent_exists=True, evals_exists=False, tmp_path=tmp_path)
        with patch("loom.services.evals_service.build_workspace_paths", return_value=mock_p):
            result = new_evals("my_agent")

        assert isinstance(result, Path)
        assert result.name == "evals.yml"


# ---------------------------------------------------------------------------
# run_evals() — EVL-SVC01 a EVL-SVC03
# ---------------------------------------------------------------------------


class TestRunEvals:
    def test_evals_yml_no_existe_lanza_evals_not_found(self):
        """EVL-SVC01: eval_file no existe → EvalsNotFoundError con nombre del agente"""
        with patch(
            "loom.services.evals_service.build_workspace_paths",
            return_value=_mock_workspace_paths(exists=False),
        ):
            with pytest.raises(EvalsNotFoundError) as exc_info:
                run_evals("my_agent")
        assert "my_agent" in str(exc_info.value)

    def test_evals_yml_existe_retorna_reports(self):
        """EVL-SVC02: eval_file existe → llama LoomEvals.run() y retorna sus reports"""
        fake_reports = [MagicMock(), MagicMock()]
        mock_evals = MagicMock()
        mock_evals.run.return_value = fake_reports

        with (
            patch(
                "loom.services.evals_service.build_workspace_paths",
                return_value=_mock_workspace_paths(exists=True),
            ),
            patch("loom.services.evals_service.LoomEvals", return_value=mock_evals),
        ):
            result = run_evals("my_agent")

        assert result == fake_reports
        mock_evals.run.assert_called_once()

    def test_loom_evals_run_falla_lanza_evals_run_error(self):
        """EVL-SVC03: LoomEvals.run() lanza excepción → EvalsRunError"""
        mock_evals = MagicMock()
        mock_evals.run.side_effect = RuntimeError("fallo interno")

        with (
            patch(
                "loom.services.evals_service.build_workspace_paths",
                return_value=_mock_workspace_paths(exists=True),
            ),
            patch("loom.services.evals_service.LoomEvals", return_value=mock_evals),
        ):
            with pytest.raises(EvalsRunError) as exc_info:
                run_evals("my_agent")

        assert "fallo interno" in str(exc_info.value)


# ---------------------------------------------------------------------------
# get_history() — EVL-SVC04 a EVL-SVC05
# ---------------------------------------------------------------------------


class TestGetHistory:
    def test_evals_yml_no_existe_lanza_evals_not_found(self):
        """EVL-SVC04: eval_file no existe → EvalsNotFoundError"""
        with patch(
            "loom.services.evals_service.build_workspace_paths",
            return_value=_mock_workspace_paths(exists=False),
        ):
            with pytest.raises(EvalsNotFoundError):
                get_history("my_agent")

    def test_retorna_historial_de_loom_evals(self):
        """EVL-SVC05: eval_file existe → retorna LoomEvals.history()"""
        fake_records = [{"run_ts": "2026-01-01", "evaluator_name": "output"}]
        mock_evals = MagicMock()
        mock_evals.history.return_value = fake_records

        with (
            patch(
                "loom.services.evals_service.build_workspace_paths",
                return_value=_mock_workspace_paths(exists=True),
            ),
            patch("loom.services.evals_service.LoomEvals", return_value=mock_evals),
        ):
            result = get_history("my_agent")

        assert result == fake_records
        mock_evals.history.assert_called_once()


# ---------------------------------------------------------------------------
# check_regression() — EVL-SVC06 a EVL-SVC07
# ---------------------------------------------------------------------------


class TestCheckRegression:
    def test_evals_yml_no_existe_lanza_evals_not_found(self):
        """EVL-SVC06: eval_file no existe → EvalsNotFoundError"""
        with patch(
            "loom.services.evals_service.build_workspace_paths",
            return_value=_mock_workspace_paths(exists=False),
        ):
            with pytest.raises(EvalsNotFoundError):
                check_regression("my_agent")

    def test_pasa_threshold_a_loom_evals_y_retorna_resultado(self):
        """EVL-SVC07: eval_file existe → llama LoomEvals.check_regression(threshold=...) y retorna resultado"""
        fake_result = {"status": "ok", "regressions": {}}
        mock_evals = MagicMock()
        mock_evals.check_regression.return_value = fake_result

        with (
            patch(
                "loom.services.evals_service.build_workspace_paths",
                return_value=_mock_workspace_paths(exists=True),
            ),
            patch("loom.services.evals_service.LoomEvals", return_value=mock_evals),
        ):
            result = check_regression("my_agent", threshold=0.1)

        assert result == fake_result
        mock_evals.check_regression.assert_called_once_with(threshold=0.1)


# ---------------------------------------------------------------------------
# get_failed_cases() — EVL-SVC08 a EVL-SVC10
# ---------------------------------------------------------------------------


class TestGetFailedCases:
    def test_evals_yml_no_existe_lanza_evals_not_found(self):
        """EVL-SVC08: eval_file no existe → EvalsNotFoundError"""
        with patch(
            "loom.services.evals_service.build_workspace_paths",
            return_value=_mock_workspace_paths(exists=False),
        ):
            with pytest.raises(EvalsNotFoundError):
                get_failed_cases("my_agent")

    def test_sin_reports_llama_failed_cases_con_none(self):
        """EVL-SVC09: reports=None → LoomEvals.failed_cases(None)"""
        mock_evals = MagicMock()
        mock_evals.failed_cases.return_value = []

        with (
            patch(
                "loom.services.evals_service.build_workspace_paths",
                return_value=_mock_workspace_paths(exists=True),
            ),
            patch("loom.services.evals_service.LoomEvals", return_value=mock_evals),
        ):
            get_failed_cases("my_agent")

        mock_evals.failed_cases.assert_called_once_with(None)

    def test_con_reports_los_pasa_a_loom_evals(self):
        """EVL-SVC10: reports=[...] → LoomEvals.failed_cases(reports)"""
        fake_reports = [MagicMock()]
        mock_evals = MagicMock()
        mock_evals.failed_cases.return_value = []

        with (
            patch(
                "loom.services.evals_service.build_workspace_paths",
                return_value=_mock_workspace_paths(exists=True),
            ),
            patch("loom.services.evals_service.LoomEvals", return_value=mock_evals),
        ):
            get_failed_cases("my_agent", reports=fake_reports)

        mock_evals.failed_cases.assert_called_once_with(fake_reports)
