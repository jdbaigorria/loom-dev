"""CLI tests for `loom evals` (plugin command)."""

from unittest.mock import MagicMock

import pytest
from typer.testing import CliRunner

from loom.cli.cli import app
from loom.core.exceptions import AgentNotFoundError
from loom_evals.exceptions import (
    EvalsAlreadyExistsError,
    EvalsNotFoundError,
    EvalsRunError,
)

runner = CliRunner()

# ---------------------------------------------------------------------------
# loom evals
# ---------------------------------------------------------------------------


class TestCliEvals:
    """CLI-EV01 a CLI-EV10"""

    # -- evals new --

    def test_evals_new_exitoso_retorna_exit_0(self, mocker, tmp_path):
        """CLI-EV00: new_evals exitoso → mensaje de éxito y exit 0"""
        mocker.patch(
            "loom_evals.cli.new_evals",
            return_value=tmp_path / "evals.yml",
        )

        result = runner.invoke(app, ["evals", "new", "my_agent"])

        assert result.exit_code == 0

    def test_evals_new_agente_no_encontrado_retorna_exit_1(self, mocker):
        """CLI-EV00b: AgentNotFoundError → exit 1"""
        mocker.patch(
            "loom_evals.cli.new_evals",
            side_effect=AgentNotFoundError("my_agent"),
        )

        result = runner.invoke(app, ["evals", "new", "my_agent"])

        assert result.exit_code == 1

    def test_evals_new_ya_existe_retorna_exit_1(self, mocker):
        """CLI-EV00c: EvalsAlreadyExistsError → exit 1"""
        mocker.patch(
            "loom_evals.cli.new_evals",
            side_effect=EvalsAlreadyExistsError("my_agent"),
        )

        result = runner.invoke(app, ["evals", "new", "my_agent"])

        assert result.exit_code == 1

    # -- evals run --

    def test_evals_run_exitoso_retorna_exit_0(self, mocker):
        """CLI-EV01: run_evals exitoso → render y exit 0"""
        mocker.patch("loom_evals.cli.run_evals", return_value=[MagicMock()])
        mocker.patch("loom_evals.cli.render_evals_results")

        result = runner.invoke(app, ["evals", "run", "my_agent"])

        assert result.exit_code == 0

    def test_evals_run_evals_not_found_retorna_exit_1(self, mocker):
        """CLI-EV02: EvalsNotFoundError → mensaje de error y exit 1"""
        mocker.patch(
            "loom_evals.cli.run_evals",
            side_effect=EvalsNotFoundError("my_agent"),
        )

        result = runner.invoke(app, ["evals", "run", "my_agent"])

        assert result.exit_code == 1

    def test_evals_run_evals_run_error_retorna_exit_1(self, mocker):
        """CLI-EV03: EvalsRunError → mensaje de error y exit 1"""
        mocker.patch(
            "loom_evals.cli.run_evals",
            side_effect=EvalsRunError("fallo al ejecutar"),
        )

        result = runner.invoke(app, ["evals", "run", "my_agent"])

        assert result.exit_code == 1

    def test_evals_run_con_flag_regression_llama_check_regression(self, mocker):
        """CLI-EV04: --regression → llama check_regression y render_evals_regression"""
        fake_reports = [MagicMock()]
        mocker.patch("loom_evals.cli.run_evals", return_value=fake_reports)
        mocker.patch("loom_evals.cli.render_evals_results")
        mock_check = mocker.patch(
            "loom_evals.cli.check_regression",
            return_value={"status": "ok", "regressions": {}},
        )
        mocker.patch("loom_evals.cli.render_evals_regression")

        runner.invoke(app, ["evals", "run", "--regression", "my_agent"])

        mock_check.assert_called_once_with("my_agent")

    def test_evals_run_con_flag_failures_llama_get_failed_cases(self, mocker):
        """CLI-EV05: --failures → llama get_failed_cases con reports y render_evals_failures"""
        fake_reports = [MagicMock()]
        mocker.patch("loom_evals.cli.run_evals", return_value=fake_reports)
        mocker.patch("loom_evals.cli.render_evals_results")
        mock_failed = mocker.patch("loom_evals.cli.get_failed_cases", return_value=[])
        mocker.patch("loom_evals.cli.render_evals_failures")

        runner.invoke(app, ["evals", "run", "--failures", "my_agent"])

        mock_failed.assert_called_once_with("my_agent", fake_reports)

    # -- evals compare --

    def test_evals_compare_con_historial_retorna_exit_0(self, mocker):
        """CLI-EV06: historial disponible → render y exit 0"""
        mocker.patch(
            "loom_evals.cli.get_history",
            return_value=[
                {"run_ts": "2026-01-01", "evaluator_name": "output", "overall_score": 0.9}
            ],
        )
        mocker.patch("loom_evals.cli.render_evals_compare")

        result = runner.invoke(app, ["evals", "compare", "my_agent"])

        assert result.exit_code == 0

    def test_evals_compare_sin_historial_retorna_exit_0_con_warning(self, mocker):
        """CLI-EV07: historial vacío → warning y exit 0 (no es error fatal)"""
        mocker.patch("loom_evals.cli.get_history", return_value=[])

        result = runner.invoke(app, ["evals", "compare", "my_agent"])

        assert result.exit_code == 0

    def test_evals_compare_evals_not_found_retorna_exit_1(self, mocker):
        """CLI-EV08: EvalsNotFoundError → exit 1"""
        mocker.patch(
            "loom_evals.cli.get_history",
            side_effect=EvalsNotFoundError("my_agent"),
        )

        result = runner.invoke(app, ["evals", "compare", "my_agent"])

        assert result.exit_code == 1

    # -- evals failures --

    def test_evals_failures_retorna_exit_0(self, mocker):
        """CLI-EV12: failures disponibles → render y exit 0"""
        mocker.patch("loom_evals.cli.get_failed_cases", return_value=[])
        mocker.patch("loom_evals.cli.render_evals_failures")

        result = runner.invoke(app, ["evals", "failures", "my_agent"])

        assert result.exit_code == 0

    def test_evals_failures_evals_not_found_retorna_exit_1(self, mocker):
        """CLI-EV13: EvalsNotFoundError → exit 1"""
        mocker.patch(
            "loom_evals.cli.get_failed_cases",
            side_effect=EvalsNotFoundError("my_agent"),
        )

        result = runner.invoke(app, ["evals", "failures", "my_agent"])

        assert result.exit_code == 1

    def test_evals_failures_llama_get_failed_cases_sin_reports(self, mocker):
        """CLI-EV14: failures desde historial → get_failed_cases llamado sin reports"""
        mock_failed = mocker.patch("loom_evals.cli.get_failed_cases", return_value=[])
        mocker.patch("loom_evals.cli.render_evals_failures")

        runner.invoke(app, ["evals", "failures", "my_agent"])

        mock_failed.assert_called_once_with("my_agent")

    # -- evals regression --

    def test_evals_regression_sin_regresiones_retorna_exit_0(self, mocker):
        """CLI-EV09: check_regression ok → render y exit 0"""
        mocker.patch(
            "loom_evals.cli.check_regression",
            return_value={"status": "ok", "regressions": {}},
        )
        mocker.patch("loom_evals.cli.render_evals_regression")

        result = runner.invoke(app, ["evals", "regression", "my_agent"])

        assert result.exit_code == 0

    def test_evals_regression_evals_not_found_retorna_exit_1(self, mocker):
        """CLI-EV10: EvalsNotFoundError → exit 1"""
        mocker.patch(
            "loom_evals.cli.check_regression",
            side_effect=EvalsNotFoundError("my_agent"),
        )

        result = runner.invoke(app, ["evals", "regression", "my_agent"])

        assert result.exit_code == 1

    def test_evals_regression_pasa_threshold_al_servicio(self, mocker):
        """CLI-EV11: --threshold 0.1 → check_regression llamado con threshold=0.1"""
        mock_check = mocker.patch(
            "loom_evals.cli.check_regression",
            return_value={"status": "ok", "regressions": {}},
        )
        mocker.patch("loom_evals.cli.render_evals_regression")

        runner.invoke(app, ["evals", "regression", "--threshold", "0.1", "my_agent"])

        mock_check.assert_called_once_with("my_agent", threshold=pytest.approx(0.1))
