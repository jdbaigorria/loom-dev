"""
tests/unit/test_loom_evals.py

Cubre loom.loom_evals.LoomEvals:
  - __init__
  - _build_task_function (flags needs_session / needs_trajectory)
  - task() (función interna)
  - run()
  - _save_reports()
  - history()
  - check_regression()
  - failed_cases()

Los tests que dependen de rutas mockean `loom.loom_evals.build_workspace_paths`.
"""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from loom.loom_evals import LoomEvals

# ---------------------------------------------------------------------------
# Helpers — evaluadores reales para flags
# ---------------------------------------------------------------------------


def _output_ev():
    from loom.adapters.strands.evals import OutputEvaluator

    return OutputEvaluator(rubric="test")


def _trajectory_ev():
    from loom.adapters.strands.evals import TrajectoryEvaluator

    return TrajectoryEvaluator(rubric="test")


def _helpfulness_ev():
    from loom.adapters.strands.evals import HelpfulnessEvaluator

    return HelpfulnessEvaluator()


def _faithfulness_ev():
    from loom.adapters.strands.evals import FaithfulnessEvaluator

    return FaithfulnessEvaluator()


def _interactions_ev():
    from loom.adapters.strands.evals import InteractionsEvaluator

    return InteractionsEvaluator(rubric="test")


def _make_case(**kwargs):
    from loom.adapters.strands.evals import Case

    defaults = {"name": "c1", "input": "¿Cuál es la capital de Francia?"}
    return Case(**{**defaults, **kwargs})


def _mock_run(answer="Paris"):
    """Fake ``DevRun`` (run_dev result): ``.response.answer`` + ``.agent.messages``."""
    run = MagicMock()
    run.response.answer = answer
    run.agent.messages = []
    return run


def _fake_report(evaluator_name="output", overall_score=0.9, run_ts="2026-01-01T00:00:00+00:00"):
    """Dict con la forma que produce report.to_dict()."""
    return {
        "run_ts": run_ts,
        "experiment": "my_agent",
        "agent": "my_agent",
        "evaluator_name": evaluator_name,
        "overall_score": overall_score,
        "cases": [],
        "test_passes": [],
        "scores": [],
        "reasons": [],
    }


# ---------------------------------------------------------------------------
# __init__ — EVL-LE01
# ---------------------------------------------------------------------------


class TestLoomEvalsInit:
    def test_name_se_asigna(self):
        """EVL-LE01: __init__(name) → self.name queda asignado"""
        ev = LoomEvals("my_agent")
        assert ev.name == "my_agent"


# ---------------------------------------------------------------------------
# _build_task_function — flags (EVL-LE02 a EVL-LE08)
# ---------------------------------------------------------------------------


class TestBuildTaskFunctionFlags:
    def test_solo_output_no_activa_telemetry(self):
        """EVL-LE02: OutputEvaluator → needs_session=False, StrandsEvalsTelemetry no se llama"""
        ev = LoomEvals("agent")
        with patch("loom.loom_evals.StrandsEvalsTelemetry") as mock_tel:
            ev._build_task_function([_output_ev()])
            mock_tel.assert_not_called()

    def test_helpfulness_activa_telemetry(self):
        """EVL-LE03: HelpfulnessEvaluator → needs_session=True, telemetry se inicializa"""
        ev = LoomEvals("agent")
        with patch("loom.loom_evals.StrandsEvalsTelemetry") as mock_tel:
            mock_tel.return_value.setup_in_memory_exporter.return_value = mock_tel.return_value
            mock_tel.return_value.in_memory_exporter = MagicMock()
            ev._build_task_function([_helpfulness_ev()])
            mock_tel.assert_called_once()

    def test_faithfulness_activa_telemetry(self):
        """EVL-LE04: FaithfulnessEvaluator → needs_session=True, telemetry se inicializa"""
        ev = LoomEvals("agent")
        with patch("loom.loom_evals.StrandsEvalsTelemetry") as mock_tel:
            mock_tel.return_value.setup_in_memory_exporter.return_value = mock_tel.return_value
            mock_tel.return_value.in_memory_exporter = MagicMock()
            ev._build_task_function([_faithfulness_ev()])
            mock_tel.assert_called_once()

    def test_interactions_activa_telemetry(self):
        """EVL-LE05: InteractionsEvaluator → needs_session=True, telemetry se inicializa"""
        ev = LoomEvals("agent")
        with patch("loom.loom_evals.StrandsEvalsTelemetry") as mock_tel:
            mock_tel.return_value.setup_in_memory_exporter.return_value = mock_tel.return_value
            mock_tel.return_value.in_memory_exporter = MagicMock()
            ev._build_task_function([_interactions_ev()])
            mock_tel.assert_called_once()

    def test_trajectory_no_activa_telemetry(self):
        """EVL-LE06: TrajectoryEvaluator → needs_session=False, telemetry no se inicializa"""
        ev = LoomEvals("agent")
        with patch("loom.loom_evals.StrandsEvalsTelemetry") as mock_tel:
            ev._build_task_function([_trajectory_ev()])
            mock_tel.assert_not_called()

    def test_mix_session_y_trajectory_activa_telemetry(self):
        """EVL-LE07: helpfulness + trajectory → needs_session=True, telemetry se inicializa"""
        ev = LoomEvals("agent")
        with patch("loom.loom_evals.StrandsEvalsTelemetry") as mock_tel:
            mock_tel.return_value.setup_in_memory_exporter.return_value = mock_tel.return_value
            mock_tel.return_value.in_memory_exporter = MagicMock()
            ev._build_task_function([_helpfulness_ev(), _trajectory_ev()])
            mock_tel.assert_called_once()

    def test_retorna_callable(self):
        """EVL-LE08: _build_task_function siempre retorna un callable"""
        ev = LoomEvals("agent")
        with patch("loom.loom_evals.StrandsEvalsTelemetry"):
            result = ev._build_task_function([_output_ev()])
            assert callable(result)


# ---------------------------------------------------------------------------
# task() — función interna (EVL-LE09 a EVL-LE14)
# ---------------------------------------------------------------------------


class TestTaskFunction:
    def test_task_retorna_task_output_con_answer(self):
        """EVL-LE09: task con OutputEvaluator → TaskOutput con output=response.answer"""
        with patch("loom.loom_evals.run_dev", return_value=_mock_run("Paris")):
            ev = LoomEvals("my_agent")
            task = ev._build_task_function([_output_ev()])
            result = task(_make_case())
        assert result["output"] == "Paris"
        assert result["trajectory"] is None

    def test_task_session_id_tiene_prefijo_eval(self):
        """EVL-LE10: task crea la session con session_id 'eval-{case.session_id}'"""
        captured = []
        with patch(
            "loom.loom_evals.run_dev",
            side_effect=lambda *a, **k: (captured.append((a, k)) or _mock_run()),
        ):
            ev = LoomEvals("my_agent")
            task = ev._build_task_function([_output_ev()])
            case = _make_case()
            task(case)

        # run_dev(name, query, session): session is the 3rd positional arg.
        session = captured[0][0][2]
        assert session.session_id == f"eval-{case.session_id}"

    def test_task_user_id_es_eval_runner(self):
        """EVL-LE11: la session se crea con user_id='eval-runner'"""
        captured = []
        with patch(
            "loom.loom_evals.run_dev",
            side_effect=lambda *a, **k: (captured.append((a, k)) or _mock_run()),
        ):
            ev = LoomEvals("my_agent")
            task = ev._build_task_function([_output_ev()])
            task(_make_case())

        session = captured[0][0][2]
        assert session.user_id == "eval-runner"

    def test_task_con_needs_session_llama_exporter_clear(self):
        """EVL-LE12: needs_session=True → exporter.clear() llamado antes de invocar agente"""
        mock_exporter = MagicMock()
        mock_exporter.get_finished_spans.return_value = []
        mock_telemetry = MagicMock()
        mock_telemetry.setup_in_memory_exporter.return_value = mock_telemetry
        mock_telemetry.in_memory_exporter = mock_exporter

        with (
            patch("loom.loom_evals.run_dev", return_value=_mock_run()),
            patch("loom.loom_evals.StrandsEvalsTelemetry", return_value=mock_telemetry),
            patch("loom.loom_evals.StrandsInMemorySessionMapper") as mock_mapper_cls,
        ):
            mock_mapper_cls.return_value.map_to_session.return_value = MagicMock()
            ev = LoomEvals("my_agent")
            task = ev._build_task_function([_helpfulness_ev()])
            task(_make_case())

        mock_exporter.clear.assert_called_once()

    def test_task_con_needs_session_mapea_spans_a_trajectory(self):
        """EVL-LE13: needs_session=True → StrandsInMemorySessionMapper en TaskOutput.trajectory"""
        fake_session = MagicMock(name="fake_session")
        mock_exporter = MagicMock()
        mock_exporter.get_finished_spans.return_value = []
        mock_telemetry = MagicMock()
        mock_telemetry.setup_in_memory_exporter.return_value = mock_telemetry
        mock_telemetry.in_memory_exporter = mock_exporter

        with (
            patch("loom.loom_evals.run_dev", return_value=_mock_run()),
            patch("loom.loom_evals.StrandsEvalsTelemetry", return_value=mock_telemetry),
            patch("loom.loom_evals.StrandsInMemorySessionMapper") as mock_mapper_cls,
        ):
            mock_mapper_cls.return_value.map_to_session.return_value = fake_session
            ev = LoomEvals("my_agent")
            task = ev._build_task_function([_helpfulness_ev()])
            result = task(_make_case())

        assert result["trajectory"] is fake_session

    def test_task_con_needs_trajectory_extrae_tools_y_actualiza_descripcion(self):
        """EVL-LE14: needs_trajectory=True → tools_use_extractor llamado, trajectory en TaskOutput"""
        fake_tools = ["tool_a", "tool_b"]

        with (
            patch("loom.loom_evals.run_dev", return_value=_mock_run()),
            patch("loom.loom_evals.tools_use_extractor") as mock_extractor,
        ):
            mock_extractor.extract_agent_tools_used_from_messages.return_value = fake_tools
            mock_extractor.extract_tools_description.return_value = {}
            ev = LoomEvals("my_agent")
            traj_ev = _trajectory_ev()
            task = ev._build_task_function([traj_ev])
            result = task(_make_case())

        assert result["trajectory"] == fake_tools
        mock_extractor.extract_agent_tools_used_from_messages.assert_called_once()


# ---------------------------------------------------------------------------
# run() — EVL-LE15 a EVL-LE17
# ---------------------------------------------------------------------------


class TestLoomEvalsRun:
    def test_run_llama_get_experiment_con_nombre_del_agente(self):
        """EVL-LE15: run() llama get_experiment(self.name)"""
        mock_experiment = MagicMock()
        mock_experiment.evaluators = [_output_ev()]
        mock_experiment.run_evaluations.return_value = []

        with (
            patch("loom.loom_evals.get_experiment", return_value=mock_experiment) as mock_get,
            patch.object(LoomEvals, "_save_reports"),
        ):
            LoomEvals("my_agent").run()
            mock_get.assert_called_once_with("my_agent")

    def test_run_retorna_reports_de_run_evaluations(self):
        """EVL-LE16: run() retorna el resultado de experiment.run_evaluations()"""
        fake_reports = [MagicMock(), MagicMock()]
        mock_experiment = MagicMock()
        mock_experiment.evaluators = [_output_ev()]
        mock_experiment.run_evaluations.return_value = fake_reports

        with (
            patch("loom.loom_evals.get_experiment", return_value=mock_experiment),
            patch.object(LoomEvals, "_save_reports"),
        ):
            result = LoomEvals("my_agent").run()

        assert result == fake_reports

    def test_run_llama_save_reports(self):
        """EVL-LE17: run() llama _save_reports con los reports obtenidos"""
        fake_reports = [MagicMock()]
        mock_experiment = MagicMock()
        mock_experiment.evaluators = [_output_ev()]
        mock_experiment.run_evaluations.return_value = fake_reports

        with (
            patch("loom.loom_evals.get_experiment", return_value=mock_experiment),
            patch.object(LoomEvals, "_save_reports") as mock_save,
        ):
            LoomEvals("my_agent").run()
            mock_save.assert_called_once_with(fake_reports)


# ---------------------------------------------------------------------------
# _save_reports() — EVL-LE18 a EVL-LE21
# ---------------------------------------------------------------------------


class TestSaveReports:
    def _make_mock_paths(self, tmp_path):
        mock_p = MagicMock()
        mock_p.eval_results_dir.return_value = tmp_path / "results"
        return mock_p

    def _make_report(self, evaluator_name="output"):
        r = MagicMock()
        r.evaluator_name = evaluator_name
        r.to_dict.return_value = {
            "evaluator_name": evaluator_name,
            "overall_score": 0.9,
            "cases": [],
            "test_passes": [],
            "scores": [],
            "reasons": [],
        }
        return r

    def test_crea_directorio_de_resultados(self, tmp_path):
        """EVL-LE18: _save_reports crea eval_results_dir si no existe"""
        mock_p = self._make_mock_paths(tmp_path)
        with patch("loom.loom_evals.build_workspace_paths", return_value=mock_p):
            LoomEvals("my_agent")._save_reports([self._make_report()])
        assert (tmp_path / "results").exists()

    def test_llama_to_file_por_cada_reporte(self, tmp_path):
        """EVL-LE19: _save_reports llama report.to_file con la ruta correcta por cada reporte"""
        mock_p = self._make_mock_paths(tmp_path)
        r1 = self._make_report("output")
        r2 = self._make_report("trajectory")

        with patch("loom.loom_evals.build_workspace_paths", return_value=mock_p):
            LoomEvals("my_agent")._save_reports([r1, r2])

        expected_dir = tmp_path / "results"
        r1.to_file.assert_called_once_with(str(expected_dir / "output.json"))
        r2.to_file.assert_called_once_with(str(expected_dir / "trajectory.json"))

    def test_escribe_jsonl_con_run_ts_y_campos_del_reporte(self, tmp_path):
        """EVL-LE20: _save_reports escribe una línea JSONL por reporte con run_ts, experiment, agent"""
        mock_p = self._make_mock_paths(tmp_path)
        report = self._make_report("output")

        with patch("loom.loom_evals.build_workspace_paths", return_value=mock_p):
            LoomEvals("my_agent")._save_reports([report])

        jsonl = (tmp_path / "results" / "results.jsonl").read_text()
        record = json.loads(jsonl.strip())
        assert record["experiment"] == "my_agent"
        assert record["agent"] == "my_agent"
        assert "run_ts" in record
        assert record["evaluator_name"] == "output"

    def test_reportes_multiples_generan_multiples_lineas_jsonl(self, tmp_path):
        """EVL-LE21: múltiples reportes → múltiples líneas en results.jsonl"""
        mock_p = self._make_mock_paths(tmp_path)
        reports = [self._make_report("output"), self._make_report("trajectory")]

        with patch("loom.loom_evals.build_workspace_paths", return_value=mock_p):
            LoomEvals("my_agent")._save_reports(reports)

        lines = (tmp_path / "results" / "results.jsonl").read_text().strip().splitlines()
        assert len(lines) == 2

    def test_reporte_sin_evaluator_name_usa_unknown(self, tmp_path):
        """EVL-LE21b: report.evaluator_name=None → nombre de archivo 'unknown.json'"""
        mock_p = self._make_mock_paths(tmp_path)
        r = self._make_report()
        r.evaluator_name = None

        with patch("loom.loom_evals.build_workspace_paths", return_value=mock_p):
            LoomEvals("my_agent")._save_reports([r])

        r.to_file.assert_called_once_with(str(tmp_path / "results" / "unknown.json"))


# ---------------------------------------------------------------------------
# history() — EVL-LE22 a EVL-LE24
# ---------------------------------------------------------------------------


class TestHistory:
    def _make_mock_paths(self, results_dir: Path):
        mock_p = MagicMock()
        mock_p.eval_results_dir.return_value = results_dir
        return mock_p

    def test_retorna_lista_vacia_si_jsonl_no_existe(self, tmp_path):
        """EVL-LE22: results.jsonl inexistente → []"""
        mock_p = self._make_mock_paths(tmp_path / "no_existe")
        with patch("loom.loom_evals.build_workspace_paths", return_value=mock_p):
            result = LoomEvals("my_agent").history()
        assert result == []

    def test_retorna_registros_del_jsonl(self, tmp_path):
        """EVL-LE23: results.jsonl con 2 líneas → lista con 2 dicts"""
        results_dir = tmp_path / "results"
        results_dir.mkdir()
        lines = [
            json.dumps(
                {
                    "run_ts": "2026-01-01T00:00:00+00:00",
                    "evaluator_name": "output",
                    "overall_score": 0.9,
                }
            ),
            json.dumps(
                {
                    "run_ts": "2026-01-01T00:00:00+00:00",
                    "evaluator_name": "trajectory",
                    "overall_score": 0.8,
                }
            ),
        ]
        (results_dir / "results.jsonl").write_text("\n".join(lines))

        mock_p = self._make_mock_paths(results_dir)
        with patch("loom.loom_evals.build_workspace_paths", return_value=mock_p):
            result = LoomEvals("my_agent").history()

        assert len(result) == 2
        assert result[0]["evaluator_name"] == "output"
        assert result[1]["evaluator_name"] == "trajectory"

    def test_ignora_lineas_vacias_en_jsonl(self, tmp_path):
        """EVL-LE24: líneas vacías en el JSONL se ignoran"""
        results_dir = tmp_path / "results"
        results_dir.mkdir()
        content = (
            json.dumps({"run_ts": "ts1", "evaluator_name": "output", "overall_score": 1.0}) + "\n\n"
        )
        (results_dir / "results.jsonl").write_text(content)

        mock_p = self._make_mock_paths(results_dir)
        with patch("loom.loom_evals.build_workspace_paths", return_value=mock_p):
            result = LoomEvals("my_agent").history()

        assert len(result) == 1


# ---------------------------------------------------------------------------
# check_regression() — EVL-LE25 a EVL-LE29
# ---------------------------------------------------------------------------


class TestCheckRegression:
    def test_sin_historial_retorna_no_history(self):
        """EVL-LE25: sin registros → {"status": "no_history"}"""
        ev = LoomEvals("my_agent")
        with patch.object(ev, "history", return_value=[]):
            result = ev.check_regression()
        assert result == {"status": "no_history"}

    def test_un_solo_run_retorna_single_run(self):
        """EVL-LE26: solo 1 timestamp → {"status": "single_run"}"""
        records = [
            _fake_report("output", 0.9, "2026-01-01T00:00:00+00:00"),
        ]
        ev = LoomEvals("my_agent")
        with patch.object(ev, "history", return_value=records):
            result = ev.check_regression()
        assert result == {"status": "single_run"}

    def test_sin_regresiones_retorna_ok(self):
        """EVL-LE27: score actual >= anterior → {"status": "ok", "regressions": {}}"""
        records = [
            _fake_report("output", 0.8, "2026-01-01T00:00:00+00:00"),
            _fake_report("output", 0.9, "2026-01-02T00:00:00+00:00"),
        ]
        ev = LoomEvals("my_agent")
        with patch.object(ev, "history", return_value=records):
            result = ev.check_regression()
        assert result["status"] == "ok"
        assert result["regressions"] == {}

    def test_regresion_detectada_cuando_delta_supera_threshold(self):
        """EVL-LE28: score baja más del threshold → status='regression' con delta correcto"""
        records = [
            _fake_report("output", 0.9, "2026-01-01T00:00:00+00:00"),
            _fake_report("output", 0.7, "2026-01-02T00:00:00+00:00"),
        ]
        ev = LoomEvals("my_agent")
        with patch.object(ev, "history", return_value=records):
            result = ev.check_regression(threshold=0.0)
        assert result["status"] == "regression"
        assert "output" in result["regressions"]
        assert result["regressions"]["output"]["previous"] == pytest.approx(0.9)
        assert result["regressions"]["output"]["current"] == pytest.approx(0.7)
        assert result["regressions"]["output"]["delta"] == pytest.approx(-0.2)

    def test_regresion_no_detectada_si_delta_dentro_del_threshold(self):
        """EVL-LE29: baja pero dentro del threshold → {"status": "ok"}"""
        records = [
            _fake_report("output", 0.9, "2026-01-01T00:00:00+00:00"),
            _fake_report("output", 0.85, "2026-01-02T00:00:00+00:00"),
        ]
        ev = LoomEvals("my_agent")
        with patch.object(ev, "history", return_value=records):
            result = ev.check_regression(threshold=0.1)
        assert result["status"] == "ok"


# ---------------------------------------------------------------------------
# failed_cases() — EVL-LE30 a EVL-LE34
# ---------------------------------------------------------------------------


class TestFailedCases:
    def test_sin_historial_y_sin_reports_retorna_lista_vacia(self):
        """EVL-LE30: history vacío y reports=None → []"""
        ev = LoomEvals("my_agent")
        with patch.object(ev, "history", return_value=[]):
            assert ev.failed_cases() == []

    def test_retorna_failures_del_ultimo_run_desde_historial(self):
        """EVL-LE31: history con 2 runs → solo los failures del último timestamp"""
        records = [
            {
                "run_ts": "2026-01-01",
                "evaluator_name": "output",
                "overall_score": 0.5,
                "cases": [
                    {"name": "c1", "input": "q", "expected_output": "a", "actual_output": "b"}
                ],
                "test_passes": [False],
                "scores": [0.2],
                "reasons": ["razón"],
            },
            {
                "run_ts": "2026-01-02",
                "evaluator_name": "output",
                "overall_score": 1.0,
                "cases": [
                    {"name": "c2", "input": "q2", "expected_output": "a2", "actual_output": "a2"}
                ],
                "test_passes": [True],
                "scores": [1.0],
                "reasons": ["ok"],
            },
        ]
        ev = LoomEvals("my_agent")
        with patch.object(ev, "history", return_value=records):
            failures = ev.failed_cases()
        # Solo el último run (2026-01-02), y ese case pasó → sin failures
        assert failures == []

    def test_case_que_falla_aparece_en_resultado(self):
        """EVL-LE32: case con test_passes[i]=False → incluido en failures"""
        records = [
            {
                "run_ts": "2026-01-01",
                "evaluator_name": "output",
                "overall_score": 0.5,
                "cases": [
                    {
                        "name": "c1",
                        "input": "pregunta",
                        "expected_output": "esperado",
                        "actual_output": "real",
                    }
                ],
                "test_passes": [False],
                "scores": [0.3],
                "reasons": ["explicación"],
            },
        ]
        ev = LoomEvals("my_agent")
        with patch.object(ev, "history", return_value=records):
            failures = ev.failed_cases()

        assert len(failures) == 1
        f = failures[0]
        assert f["case"] == "c1"
        assert f["evaluator"] == "output"
        assert f["score"] == pytest.approx(0.3)
        assert f["reason"] == "explicación"
        assert f["input"] == "pregunta"
        assert f["expected"] == "esperado"
        assert f["actual"] == "real"

    def test_con_reports_arg_usa_to_dict(self):
        """EVL-LE33: reports=[...] provistos → llama report.to_dict(), no usa history()"""
        mock_report = MagicMock()
        mock_report.to_dict.return_value = {
            "evaluator_name": "output",
            "overall_score": 1.0,
            "cases": [],
            "test_passes": [],
            "scores": [],
            "reasons": [],
        }
        ev = LoomEvals("my_agent")
        with patch.object(ev, "history") as mock_hist:
            ev.failed_cases(reports=[mock_report])
            mock_hist.assert_not_called()
        mock_report.to_dict.assert_called_once()

    def test_case_que_pasa_no_aparece_en_failures(self):
        """EVL-LE34: case con test_passes[i]=True → no incluido en failures"""
        records = [
            {
                "run_ts": "2026-01-01",
                "evaluator_name": "output",
                "overall_score": 1.0,
                "cases": [
                    {"name": "c1", "input": "q", "expected_output": "a", "actual_output": "a"}
                ],
                "test_passes": [True],
                "scores": [1.0],
                "reasons": ["correcto"],
            },
        ]
        ev = LoomEvals("my_agent")
        with patch.object(ev, "history", return_value=records):
            assert ev.failed_cases() == []
