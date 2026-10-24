"""
tests/unit/test_evaluator.py

Cubre loom_evals.loader:
  - _to_case
  - _to_evaluator
  - _load_experiment
  - get_experiment
"""

import textwrap
from pathlib import Path

import pytest

from loom_evals.loader import _load_experiment, _to_case, _to_evaluator, get_experiment
from loom_evals.schemas import CaseConfig, EvaluatorConfig

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _case_cfg(**kwargs) -> CaseConfig:
    defaults = {"name": "c1", "input": "¿Cuál es la capital de Francia?"}
    return CaseConfig(**{**defaults, **kwargs})


def _eval_cfg(**kwargs) -> EvaluatorConfig:
    defaults = {"type": "output", "rubric": "¿La respuesta es correcta?"}
    return EvaluatorConfig(**{**defaults, **kwargs})


def _make_paths(tmp_path):
    from loom.core.paths import WorkspacePaths

    return WorkspacePaths(project_root=tmp_path, workspace_name="warp")


def _write_eval_yaml(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(content), encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# _to_case — EVL-C01 a EVL-C04
# ---------------------------------------------------------------------------


class TestToCase:
    """EVL-C01 a EVL-C04"""

    def test_convierte_config_a_case_de_strands(self):
        """EVL-C01: CaseConfig básico → strands Case con name e input"""
        from loom_evals.adapters.strands_evals import Case

        result = _to_case([_case_cfg()])
        assert len(result) == 1
        assert isinstance(result[0], Case)
        assert result[0].name == "c1"
        assert result[0].input == "¿Cuál es la capital de Francia?"

    def test_campos_none_no_se_pasan_al_constructor(self):
        """EVL-C02: campos None no se incluyen en kwargs → strands usa sus propios defaults"""
        result = _to_case([_case_cfg()])
        assert result[0].expected_output is None

    def test_campos_con_valor_se_pasan_correctamente(self):
        """EVL-C03: expected_output y expected_trajectory provistos → llegan al Case de strands"""
        result = _to_case(
            [
                _case_cfg(
                    expected_output="Paris",
                    expected_trajectory=["tool_a", "tool_b"],
                )
            ]
        )
        assert result[0].expected_output == "Paris"
        assert result[0].expected_trajectory == ["tool_a", "tool_b"]

    def test_lista_vacia_retorna_lista_vacia(self):
        """EVL-C04: lista vacía → retorna lista vacía"""
        assert _to_case([]) == []


# ---------------------------------------------------------------------------
# _to_evaluator — tipos con rubric (EVL-E01 a EVL-E06)
# ---------------------------------------------------------------------------


class TestToEvaluatorWithRubric:
    """EVL-E01 a EVL-E06"""

    def test_output_retorna_output_evaluator(self):
        """EVL-E01: type='output' → OutputEvaluator con rubric"""
        from loom_evals.adapters.strands_evals import OutputEvaluator

        result = _to_evaluator([_eval_cfg(type="output")])
        assert isinstance(result[0], OutputEvaluator)
        assert result[0].rubric == "¿La respuesta es correcta?"

    def test_trajectory_retorna_trajectory_evaluator(self):
        """EVL-E02: type='trajectory' → TrajectoryEvaluator con rubric"""
        from loom_evals.adapters.strands_evals import TrajectoryEvaluator

        result = _to_evaluator([_eval_cfg(type="trajectory")])
        assert isinstance(result[0], TrajectoryEvaluator)
        assert result[0].rubric == "¿La respuesta es correcta?"

    def test_interactions_retorna_interactions_evaluator(self):
        """EVL-E03: type='interactions' → InteractionsEvaluator con rubric"""
        from loom_evals.adapters.strands_evals import InteractionsEvaluator

        result = _to_evaluator([_eval_cfg(type="interactions")])
        assert isinstance(result[0], InteractionsEvaluator)

    def test_trajectory_con_trajectory_description_lo_incluye(self):
        """EVL-E04: type='trajectory' + trajectory_description → pasa al constructor"""
        result = _to_evaluator(
            [
                _eval_cfg(
                    type="trajectory",
                    trajectory_description={"step": "descripción del paso"},
                )
            ]
        )
        assert result[0].trajectory_description == {"step": "descripción del paso"}

    def test_interactions_con_interaction_description_lo_incluye(self):
        """EVL-E05: type='interactions' + interaction_description → pasa al constructor"""
        result = _to_evaluator(
            [
                _eval_cfg(
                    type="interactions",
                    interaction_description={"role": "user"},
                )
            ]
        )
        assert result[0].interaction_description == {"role": "user"}

    def test_lista_vacia_retorna_lista_vacia(self):
        """EVL-E06: lista vacía → retorna lista vacía"""
        assert _to_evaluator([]) == []


# ---------------------------------------------------------------------------
# _to_evaluator — exclusión de campos según tipo (EVL-E07 a EVL-E12)
# ---------------------------------------------------------------------------


class TestToEvaluatorFieldExclusion:
    """EVL-E07 a EVL-E12"""

    def test_output_excluye_trajectory_description(self):
        """EVL-E07: type='output' + trajectory_description → no llega al evaluador"""
        result = _to_evaluator(
            [
                _eval_cfg(
                    type="output",
                    trajectory_description={"step": "x"},
                )
            ]
        )
        assert (
            not hasattr(result[0], "trajectory_description")
            or result[0].trajectory_description is None
        )

    def test_output_excluye_interaction_description(self):
        """EVL-E08: type='output' + interaction_description → no llega al evaluador"""
        result = _to_evaluator(
            [
                _eval_cfg(
                    type="output",
                    interaction_description={"role": "user"},
                )
            ]
        )
        assert (
            not hasattr(result[0], "interaction_description")
            or result[0].interaction_description is None
        )

    def test_trajectory_excluye_interaction_description(self):
        """EVL-E09: type='trajectory' + interaction_description → no llega al evaluador"""
        result = _to_evaluator(
            [
                _eval_cfg(
                    type="trajectory",
                    interaction_description={"role": "user"},
                )
            ]
        )
        assert (
            not hasattr(result[0], "interaction_description")
            or result[0].interaction_description is None
        )

    def test_interactions_excluye_trajectory_description(self):
        """EVL-E10: type='interactions' + trajectory_description → no llega al evaluador"""
        result = _to_evaluator(
            [
                _eval_cfg(
                    type="interactions",
                    trajectory_description={"step": "x"},
                )
            ]
        )
        assert (
            not hasattr(result[0], "trajectory_description")
            or result[0].trajectory_description is None
        )

    def test_type_nunca_se_pasa_al_constructor(self):
        """EVL-E11: 'type' siempre excluido → constructor no recibe ese kwarg"""
        result = _to_evaluator([_eval_cfg(type="output")])
        assert len(result) == 1  # construyó sin TypeError

    def test_campos_none_excluidos_para_todos_los_tipos(self):
        """EVL-E12: campos opcionales None no se pasan al constructor (exclude_none=True)"""
        result = _to_evaluator([_eval_cfg(type="output", model=None, system_prompt=None)])
        assert result[0].model is None


# ---------------------------------------------------------------------------
# _to_evaluator — tipos sin rubric (EVL-E13 a EVL-E17)
# ---------------------------------------------------------------------------

class TestToEvaluatorNoRubric:
    """EVL-E13 a EVL-E17"""

    def test_helpfulness_retorna_evaluador_correcto_sin_rubric(self):
        """EVL-E13: type='helpfulness' → HelpfulnessEvaluator, rubric excluido"""
        from loom_evals.adapters.strands_evals import HelpfulnessEvaluator

        result = _to_evaluator([_eval_cfg(type="helpfulness")])
        assert isinstance(result[0], HelpfulnessEvaluator)

    def test_faithfulness_retorna_evaluador_correcto_sin_rubric(self):
        """EVL-E14: type='faithfulness' → FaithfulnessEvaluator, rubric excluido"""
        from loom_evals.adapters.strands_evals import FaithfulnessEvaluator

        result = _to_evaluator([_eval_cfg(type="faithfulness")])
        assert isinstance(result[0], FaithfulnessEvaluator)

    def test_goal_success_rate_retorna_evaluador_correcto_sin_rubric(self):
        """EVL-E15: type='goal_success_rate' → GoalSuccessRateEvaluator, rubric excluido"""
        from loom_evals.adapters.strands_evals import GoalSuccessRateEvaluator

        result = _to_evaluator([_eval_cfg(type="goal_success_rate")])
        assert isinstance(result[0], GoalSuccessRateEvaluator)

    def test_tool_selection_retorna_evaluador_correcto_sin_rubric(self):
        """EVL-E16: type='tool_selection' → ToolSelectionAccuracyEvaluator, rubric excluido"""
        from loom_evals.adapters.strands_evals import ToolSelectionAccuracyEvaluator

        result = _to_evaluator([_eval_cfg(type="tool_selection")])
        assert isinstance(result[0], ToolSelectionAccuracyEvaluator)

    def test_tool_parameter_retorna_evaluador_correcto_sin_rubric(self):
        """EVL-E17: type='tool_parameter' → ToolParameterAccuracyEvaluator, rubric excluido"""
        from loom_evals.adapters.strands_evals import ToolParameterAccuracyEvaluator

        result = _to_evaluator([_eval_cfg(type="tool_parameter")])
        assert isinstance(result[0], ToolParameterAccuracyEvaluator)


# ---------------------------------------------------------------------------
# _load_experiment — EVL-L01 a EVL-L03
# ---------------------------------------------------------------------------


class TestLoadExperiment:
    """EVL-L01 a EVL-L03"""

    def test_carga_yaml_y_retorna_experiment_config(self, monkeypatch, tmp_path):
        """EVL-L01: YAML válido → ExperimentConfig con cases y evaluators"""
        from loom_evals.schemas import ExperimentConfig

        yaml_path = tmp_path / "warp" / "agents" / "my_agent" / "evals" / "evals.yml"
        _write_eval_yaml(
            yaml_path,
            """\
            cases:
              - name: caso_1
                input: ¿Cuál es la capital de Francia?
                expected_output: Paris
            evaluators:
              - type: output
                rubric: ¿La respuesta es correcta?
        """,
        )
        monkeypatch.setattr(
            "loom_evals.loader.build_workspace_paths",
            lambda **_: _make_paths(tmp_path),
        )

        result = _load_experiment("my_agent")
        assert isinstance(result, ExperimentConfig)
        assert len(result.cases) == 1
        assert result.cases[0].name == "caso_1"
        assert result.evaluators[0].type == "output"

    def test_yaml_con_multiples_cases_y_evaluadores(self, monkeypatch, tmp_path):
        """EVL-L02: YAML con 2 cases y 2 evaluadores → ExperimentConfig completo"""
        yaml_path = tmp_path / "warp" / "agents" / "my_agent" / "evals" / "evals.yml"
        _write_eval_yaml(
            yaml_path,
            """\
            cases:
              - name: c1
                input: input_1
              - name: c2
                input: input_2
            evaluators:
              - type: output
                rubric: rubric_1
              - type: helpfulness
                rubric: rubric_2
        """,
        )
        monkeypatch.setattr(
            "loom_evals.loader.build_workspace_paths",
            lambda **_: _make_paths(tmp_path),
        )

        result = _load_experiment("my_agent")
        assert len(result.cases) == 2
        assert len(result.evaluators) == 2

    def test_yaml_inexistente_lanza_error(self, monkeypatch, tmp_path):
        """EVL-L03: archivo YAML inexistente → FileNotFoundError"""
        monkeypatch.setattr(
            "loom_evals.loader.build_workspace_paths",
            lambda **_: _make_paths(tmp_path),
        )
        with pytest.raises(Exception):
            _load_experiment("agent_inexistente")


# ---------------------------------------------------------------------------
# get_experiment — EVL-G01 a EVL-G02
# ---------------------------------------------------------------------------


class TestGetExperiment:
    """EVL-G01 a EVL-G02"""

    def test_retorna_experiment_de_strands_con_cases_y_evaluadores(self, monkeypatch, tmp_path):
        """EVL-G01: YAML válido → strands_evals.Experiment con Case y OutputEvaluator"""
        from loom_evals.adapters.strands_evals import Experiment, OutputEvaluator

        yaml_path = tmp_path / "warp" / "agents" / "my_agent" / "evals" / "evals.yml"
        _write_eval_yaml(
            yaml_path,
            """\
            cases:
              - name: caso_1
                input: ¿Cuál es la capital de Francia?
                expected_output: Paris
            evaluators:
              - type: output
                rubric: ¿La respuesta es correcta?
        """,
        )
        monkeypatch.setattr(
            "loom_evals.loader.build_workspace_paths",
            lambda **_: _make_paths(tmp_path),
        )

        result = get_experiment("my_agent")
        assert isinstance(result, Experiment)
        assert len(result.cases) == 1
        assert result.cases[0].name == "caso_1"
        assert isinstance(result.evaluators[0], OutputEvaluator)

    def test_multiples_tipos_de_evaluadores_se_mapean_correctamente(self, monkeypatch, tmp_path):
        """EVL-G02: YAML con output + trajectory + helpfulness → instancias correctas"""
        from loom_evals.adapters.strands_evals import (
            HelpfulnessEvaluator,
            OutputEvaluator,
            TrajectoryEvaluator,
        )

        yaml_path = tmp_path / "warp" / "agents" / "my_agent" / "evals" / "evals.yml"
        _write_eval_yaml(
            yaml_path,
            """\
            cases:
              - name: c1
                input: input
            evaluators:
              - type: output
                rubric: rubric_output
              - type: trajectory
                rubric: rubric_traj
              - type: helpfulness
                rubric: rubric_help
        """,
        )
        monkeypatch.setattr(
            "loom_evals.loader.build_workspace_paths",
            lambda **_: _make_paths(tmp_path),
        )

        result = get_experiment("my_agent")
        types = [type(e) for e in result.evaluators]
        assert OutputEvaluator in types
        assert TrajectoryEvaluator in types
        assert HelpfulnessEvaluator in types
