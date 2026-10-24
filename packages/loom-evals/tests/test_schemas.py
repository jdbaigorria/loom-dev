"""Schema tests for eval cases, evaluators, and experiments."""

import logging

import pytest
from pydantic import ValidationError

from loom_evals.schemas import CaseConfig as Case
from loom_evals.schemas import EvaluatorConfig as Evaluator
from loom_evals.schemas import ExperimentConfig as Experiment

# ---------------------------------------------------------------------------
# Case — SCH-EV
# ---------------------------------------------------------------------------


class TestCase:
    """SCH-EV01 a SCH-EV12"""

    def test_campos_requeridos_se_asignan(self):
        """SCH-EV01: name e input son requeridos y se asignan correctamente"""
        case = Case(name="test_case", input="¿Cuál es la capital de Francia?")
        assert case.name == "test_case"
        assert case.input == "¿Cuál es la capital de Francia?"

    def test_campos_opcionales_son_none_por_defecto(self):
        """SCH-EV02: todos los campos opcionales son None por defecto"""
        case = Case(name="test_case", input="input")
        assert case.expected_output is None
        assert case.expected_trajectory is None
        assert case.expected_interactions is None
        assert case.expected_environment_state is None
        assert case.metadata is None

    def test_sin_name_lanza_validation_error(self):
        """SCH-EV03: omitir name → ValidationError"""
        with pytest.raises(ValidationError):
            Case(input="input")

    def test_sin_input_lanza_validation_error(self):
        """SCH-EV04: omitir input → ValidationError"""
        with pytest.raises(ValidationError):
            Case(name="test_case")

    def test_todos_los_campos_opcionales_se_asignan(self):
        """SCH-EV05: todos los campos opcionales provistos → se conservan"""
        case = Case(
            name="full_case",
            input="input",
            expected_output="output",
            expected_trajectory=["step1", "step2"],
            expected_interactions=[{"role": "user", "content": "hola"}],
            expected_environment_state=[{"key": "value"}],
            metadata={"author": "javier"},
        )
        assert case.expected_output == "output"
        assert case.expected_trajectory == ["step1", "step2"]
        assert case.expected_interactions == [{"role": "user", "content": "hola"}]
        assert case.expected_environment_state == [{"key": "value"}]
        assert case.metadata == {"author": "javier"}

    def test_validate_for_evaluator_output_sin_expected_output_genera_warning(self):
        """SCH-EV06: evaluator 'output' sin expected_output → warning con nombre del campo"""
        case = Case(name="my_case", input="input")
        warnings = case.validate_for_evaluator("output")
        assert len(warnings) == 1
        assert "my_case" in warnings[0]
        assert "expected_output" in warnings[0]
        assert "output" in warnings[0]

    def test_validate_for_evaluator_output_con_expected_output_no_genera_warnings(self):
        """SCH-EV07: evaluator 'output' con expected_output presente → lista vacía"""
        case = Case(name="my_case", input="input", expected_output="Paris")
        warnings = case.validate_for_evaluator("output")
        assert warnings == []

    def test_validate_for_evaluator_trajectory_sin_campo_genera_warning(self):
        """SCH-EV08: evaluator 'trajectory' sin expected_trajectory → warning"""
        case = Case(name="traj_case", input="input")
        warnings = case.validate_for_evaluator("trajectory")
        assert len(warnings) == 1
        assert "traj_case" in warnings[0]
        assert "expected_trajectory" in warnings[0]

    def test_validate_for_evaluator_trajectory_con_campo_no_genera_warnings(self):
        """SCH-EV09: evaluator 'trajectory' con expected_trajectory → lista vacía"""
        case = Case(name="traj_case", input="input", expected_trajectory=["a", "b"])
        warnings = case.validate_for_evaluator("trajectory")
        assert warnings == []

    def test_validate_for_evaluator_interactions_sin_campo_genera_warning(self):
        """SCH-EV10: evaluator 'interactions' sin expected_interactions → warning"""
        case = Case(name="inter_case", input="input")
        warnings = case.validate_for_evaluator("interactions")
        assert len(warnings) == 1
        assert "inter_case" in warnings[0]
        assert "expected_interactions" in warnings[0]

    def test_validate_for_evaluator_interactions_con_campo_no_genera_warnings(self):
        """SCH-EV11: evaluator 'interactions' con expected_interactions → lista vacía"""
        case = Case(
            name="inter_case",
            input="input",
            expected_interactions=[{"role": "user", "content": "hi"}],
        )
        warnings = case.validate_for_evaluator("interactions")
        assert warnings == []

    def test_validate_for_evaluator_tipo_desconocido_retorna_lista_vacia(self):
        """SCH-EV12: evaluator type desconocido → no se requieren campos, lista vacía"""
        case = Case(name="my_case", input="input")
        warnings = case.validate_for_evaluator("unknown_evaluator")
        assert warnings == []


# ---------------------------------------------------------------------------
# Evaluator — SCH-EVL
# ---------------------------------------------------------------------------


VALID_TYPES = [
    "output",
    "trajectory",
    "interactions",
    "helpfulness",
    "faithfulness",
    "goal_success_rate",
    "tool_selection",
    "tool_parameter",
]


class TestEvaluator:
    """SCH-EVL01 a SCH-EVL20"""

    # --- Construcción ---

    def test_type_y_rubric_son_requeridos(self):
        """SCH-EVL01: type y rubric son requeridos"""
        ev = Evaluator(type="output", rubric="¿La respuesta es correcta?")
        assert ev.type == "output"
        assert ev.rubric == "¿La respuesta es correcta?"

    def test_sin_type_lanza_validation_error(self):
        """SCH-EVL02: omitir type → ValidationError"""
        with pytest.raises(ValidationError):
            Evaluator(rubric="rubric")

    def test_sin_rubric_lanza_validation_error(self):
        """SCH-EVL03: omitir rubric → ValidationError"""
        with pytest.raises(ValidationError):
            Evaluator(type="output")

    def test_type_invalido_lanza_validation_error(self):
        """SCH-EVL04: type fuera del Literal → ValidationError"""
        with pytest.raises(ValidationError):
            Evaluator(type="unknown_type", rubric="rubric")

    @pytest.mark.parametrize("evaluator_type", VALID_TYPES)
    def test_todos_los_tipos_literales_son_validos(self, evaluator_type):
        """SCH-EVL05: todos los valores del Literal son aceptados"""
        ev = Evaluator(type=evaluator_type, rubric="rubric")
        assert ev.type == evaluator_type

    def test_campos_opcionales_son_none_por_defecto(self):
        """SCH-EVL06: campos opcionales son None y include_inputs=True por defecto"""
        ev = Evaluator(type="output", rubric="rubric")
        assert ev.interaction_description is None
        assert ev.trajectory_description is None
        assert ev.model is None
        assert ev.system_prompt is None
        assert ev.include_inputs is True

    def test_todos_los_campos_se_asignan(self):
        """SCH-EVL07: todos los campos provistos → se conservan"""
        ev = Evaluator(
            type="trajectory",
            rubric="rubric",
            interaction_description={"step": "descripción"},
            trajectory_description={"step": "trayectoria"},
            model="claude-3",
            system_prompt="Eres un evaluador.",
            include_inputs=False,
        )
        assert ev.interaction_description == {"step": "descripción"}
        assert ev.trajectory_description == {"step": "trayectoria"}
        assert ev.model == "claude-3"
        assert ev.system_prompt == "Eres un evaluador."
        assert ev.include_inputs is False

    # --- validate_for_type: tipos sin field_map (retornan lista vacía) ---

    @pytest.mark.parametrize(
        "evaluator_type",
        ["helpfulness", "faithfulness", "goal_success_rate", "tool_selection", "tool_parameter"],
    )
    def test_tipos_sin_field_map_retornan_lista_vacia(self, evaluator_type):
        """SCH-EVL08: tipos fuera del field_map → sin warnings sin importar campos presentes"""
        ev = Evaluator(
            type=evaluator_type,
            rubric="rubric",
            trajectory_description={"a": "b"},
            interaction_description={"c": "d"},
        )
        assert ev.validate_for_type() == []

    # --- validate_for_type: output ---

    def test_output_sin_campos_irrelevantes_no_genera_warnings(self):
        """SCH-EVL09: tipo 'output' sin trajectory_description ni interaction_description → sin warnings"""
        ev = Evaluator(type="output", rubric="rubric")
        assert ev.validate_for_type() == []

    def test_output_con_trajectory_description_genera_warning(self):
        """SCH-EVL10: tipo 'output' con trajectory_description → warning de campo ignorado"""
        ev = Evaluator(type="output", rubric="rubric", trajectory_description={"step": "x"})
        warnings = ev.validate_for_type()
        assert len(warnings) == 1
        assert "trajectory_description" in warnings[0]
        assert "output" in warnings[0]

    def test_output_con_interaction_description_genera_warning(self):
        """SCH-EVL11: tipo 'output' con interaction_description → warning de campo ignorado"""
        ev = Evaluator(type="output", rubric="rubric", interaction_description={"step": "x"})
        warnings = ev.validate_for_type()
        assert len(warnings) == 1
        assert "interaction_description" in warnings[0]

    def test_output_con_ambos_campos_irrelevantes_genera_dos_warnings(self):
        """SCH-EVL12: tipo 'output' con ambos campos irrelevantes → 2 warnings"""
        ev = Evaluator(
            type="output",
            rubric="rubric",
            trajectory_description={"a": "b"},
            interaction_description={"c": "d"},
        )
        warnings = ev.validate_for_type()
        assert len(warnings) == 2

    # --- validate_for_type: trajectory ---

    def test_trajectory_sin_trajectory_description_genera_warning_de_recomendado(self):
        """SCH-EVL13: tipo 'trajectory' sin trajectory_description → warning de campo recomendado"""
        ev = Evaluator(type="trajectory", rubric="rubric")
        warnings = ev.validate_for_type()
        assert len(warnings) == 1
        assert "trajectory_description" in warnings[0]
        assert "trajectory" in warnings[0]

    def test_trajectory_con_trajectory_description_no_genera_warning_relevant(self):
        """SCH-EVL14: tipo 'trajectory' con trajectory_description → no hay warning de faltante"""
        ev = Evaluator(type="trajectory", rubric="rubric", trajectory_description={"step": "x"})
        warnings = ev.validate_for_type()
        assert not any("trajectory_description" in w and "recommended" in w for w in warnings)

    def test_trajectory_con_interaction_description_genera_warning_irrelevante(self):
        """SCH-EVL15: tipo 'trajectory' con ambos campos → warning por interaction_description ignorado"""
        ev = Evaluator(
            type="trajectory",
            rubric="rubric",
            trajectory_description={"step": "x"},
            interaction_description={"role": "user"},
        )
        warnings = ev.validate_for_type()
        assert any("interaction_description" in w for w in warnings)

    def test_trajectory_con_ambos_campos_solo_genera_warning_irrelevante(self):
        """SCH-EVL16: tipo 'trajectory' con ambos campos → solo warning por interaction_description"""
        ev = Evaluator(
            type="trajectory",
            rubric="rubric",
            trajectory_description={"a": "b"},
            interaction_description={"c": "d"},
        )
        warnings = ev.validate_for_type()
        assert len(warnings) == 1
        assert "interaction_description" in warnings[0]

    # --- validate_for_type: interactions ---

    def test_interactions_sin_interaction_description_genera_warning_de_recomendado(self):
        """SCH-EVL17: tipo 'interactions' sin interaction_description → warning de campo recomendado"""
        ev = Evaluator(type="interactions", rubric="rubric")
        warnings = ev.validate_for_type()
        assert len(warnings) == 1
        assert "interaction_description" in warnings[0]
        assert "interactions" in warnings[0]

    def test_interactions_con_interaction_description_no_genera_warning_relevant(self):
        """SCH-EVL18: tipo 'interactions' con interaction_description → no hay warning de faltante"""
        ev = Evaluator(
            type="interactions", rubric="rubric", interaction_description={"role": "user"}
        )
        warnings = ev.validate_for_type()
        assert not any("interaction_description" in w and "recommended" in w for w in warnings)

    def test_interactions_con_trajectory_description_genera_warning_irrelevante(self):
        """SCH-EVL19: tipo 'interactions' con ambos campos → warning por trajectory_description ignorado"""
        ev = Evaluator(
            type="interactions",
            rubric="rubric",
            interaction_description={"role": "user"},
            trajectory_description={"step": "x"},
        )
        warnings = ev.validate_for_type()
        assert any("trajectory_description" in w for w in warnings)

    def test_interactions_con_ambos_campos_solo_genera_warning_irrelevante(self):
        """SCH-EVL20: tipo 'interactions' con ambos campos → solo warning por trajectory_description"""
        ev = Evaluator(
            type="interactions",
            rubric="rubric",
            interaction_description={"a": "b"},
            trajectory_description={"c": "d"},
        )
        warnings = ev.validate_for_type()
        assert len(warnings) == 1
        assert "trajectory_description" in warnings[0]


# ---------------------------------------------------------------------------
# Experiment — SCH-EXP
# ---------------------------------------------------------------------------


def _case(name="c1", input="input", **kwargs) -> Case:
    return Case(name=name, input=input, **kwargs)


def _evaluator(type="output", rubric="rubric", **kwargs) -> Evaluator:
    return Evaluator(type=type, rubric=rubric, **kwargs)


class TestExperiment:
    """SCH-EXP01 a SCH-EXP12"""

    # --- Construcción ---

    def test_cases_y_evaluators_requeridos(self):
        """SCH-EXP01: cases y evaluators son requeridos"""
        exp = Experiment(cases=[_case()], evaluators=[_evaluator()])
        assert len(exp.cases) == 1
        assert len(exp.evaluators) == 1

    def test_sin_cases_lanza_validation_error(self):
        """SCH-EXP02: omitir cases → ValidationError"""
        with pytest.raises(ValidationError):
            Experiment(evaluators=[_evaluator()])

    def test_sin_evaluators_lanza_validation_error(self):
        """SCH-EXP03: omitir evaluators → ValidationError"""
        with pytest.raises(ValidationError):
            Experiment(cases=[_case()])

    def test_listas_vacias_son_validas(self):
        """SCH-EXP04: listas vacías son aceptadas por pydantic"""
        exp = Experiment(cases=[], evaluators=[])
        assert exp.cases == []
        assert exp.evaluators == []

    # --- cross_validate: sin warnings ---

    def test_case_completo_con_evaluador_output_no_emite_warnings(self, caplog):
        """SCH-EXP05: case con expected_output + evaluador output → sin warnings loggeados"""

        with caplog.at_level(logging.WARNING, logger="loom.evals"):
            Experiment(
                cases=[_case(expected_output="Paris")],
                evaluators=[_evaluator(type="output")],
            )
        assert caplog.records == []

    def test_tipos_sin_field_map_no_emiten_warnings(self, caplog):
        """SCH-EXP06: evaluadores helpfulness/faithfulness/etc. → sin warnings loggeados"""

        with caplog.at_level(logging.WARNING, logger="loom.evals"):
            Experiment(
                cases=[_case()],
                evaluators=[
                    _evaluator(type="helpfulness"),
                    _evaluator(type="faithfulness"),
                    _evaluator(type="goal_success_rate"),
                ],
            )
        assert caplog.records == []

    # --- cross_validate: warnings de case ---

    def test_case_sin_expected_output_con_evaluador_output_loggea_warning(self, caplog):
        """SCH-EXP07: case sin expected_output + evaluador output → warning loggeado con nombre del case"""

        with caplog.at_level(logging.WARNING, logger="loom.evals"):
            Experiment(
                cases=[_case(name="mi_case")],
                evaluators=[_evaluator(type="output")],
            )
        assert len(caplog.records) == 1
        assert "mi_case" in caplog.records[0].message
        assert "expected_output" in caplog.records[0].message

    def test_case_sin_expected_trajectory_con_evaluador_trajectory_loggea_warning(self, caplog):
        """SCH-EXP08: case sin expected_trajectory + evaluador trajectory → warning loggeado"""

        with caplog.at_level(logging.WARNING, logger="loom.evals"):
            Experiment(
                cases=[_case(name="traj_case")],
                evaluators=[_evaluator(type="trajectory")],
            )
        assert any(
            "traj_case" in r.message and "expected_trajectory" in r.message for r in caplog.records
        )

    def test_case_sin_expected_interactions_con_evaluador_interactions_loggea_warning(self, caplog):
        """SCH-EXP09: case sin expected_interactions + evaluador interactions → warning loggeado"""

        with caplog.at_level(logging.WARNING, logger="loom.evals"):
            Experiment(
                cases=[_case(name="inter_case")],
                evaluators=[_evaluator(type="interactions")],
            )
        assert any(
            "inter_case" in r.message and "expected_interactions" in r.message
            for r in caplog.records
        )

    # --- cross_validate: warnings de evaluador ---

    def test_evaluador_con_campo_irrelevante_loggea_warning(self, caplog):
        """SCH-EXP10: evaluador output con trajectory_description → warning de campo ignorado"""

        with caplog.at_level(logging.WARNING, logger="loom.evals"):
            Experiment(
                cases=[_case(expected_output="ok")],
                evaluators=[_evaluator(type="output", trajectory_description={"step": "x"})],
            )
        assert any("trajectory_description" in r.message for r in caplog.records)

    # --- cross_validate: producto cruzado ---

    def test_multiples_cases_y_evaluadores_generan_warning_por_cada_combinacion(self, caplog):
        """SCH-EXP11: 2 cases sin expected_output × 1 evaluador output → 2 warnings"""

        with caplog.at_level(logging.WARNING, logger="loom.evals"):
            Experiment(
                cases=[_case(name="c1"), _case(name="c2")],
                evaluators=[_evaluator(type="output")],
            )
        mensajes = [r.message for r in caplog.records]
        assert any("c1" in m for m in mensajes)
        assert any("c2" in m for m in mensajes)

    def test_multiples_evaluadores_generan_warnings_por_cada_uno(self, caplog):
        """SCH-EXP12: 1 case sin campos × evaluadores output+trajectory+interactions → 3 warnings de case"""

        with caplog.at_level(logging.WARNING, logger="loom.evals"):
            Experiment(
                cases=[_case(name="solo_case")],
                evaluators=[
                    _evaluator(type="output"),
                    _evaluator(type="trajectory"),
                    _evaluator(type="interactions"),
                ],
            )
        mensajes = [r.message for r in caplog.records if "solo_case" in r.message]
        assert len(mensajes) == 3
