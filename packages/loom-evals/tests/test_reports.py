"""Report-shape normalization across strands-agents-evals versions."""

import importlib.metadata as metadata

from loom_evals.adapters.strands_evals import (
    Case,
    EvaluationOutput,
    Evaluator,
    Experiment,
    split_reports,
)
from loom_evals.loader import _to_evaluator
from loom_evals.schemas import EvaluatorConfig


class Always(Evaluator):
    def evaluate(self, data):
        return [EvaluationOutput(score=1.0, test_pass=True, reason="ok")]

    async def evaluate_async(self, data):
        return self.evaluate(data)


def test_split_reports_real_experiment_without_llm(tmp_path):
    version = metadata.version("strands-agents-evals")
    legacy = version.startswith(("0.1.", "0.2."))
    evaluators = [Always(), Always()] if legacy else [Always(name="a"), Always(name="b")]
    result = Experiment(
        cases=[Case(name="c1", input="hi")],
        evaluators=evaluators,
    ).run_evaluations(lambda case: "hello")
    names = ["a", "b"]
    pairs = split_reports(result, names)
    assert [name for name, _ in pairs] == names
    assert len(pairs) == 2


def test_all_default_evaluator_types_construct():
    types = [
        "output",
        "trajectory",
        "interactions",
        "helpfulness",
        "faithfulness",
        "goal_success_rate",
        "tool_selection",
        "tool_parameter",
    ]
    built = _to_evaluator([EvaluatorConfig(type=kind, rubric="r") for kind in types])
    assert len(built) == len(types)


def test_duplicate_types_get_distinct_names():
    built = _to_evaluator(
        [
            EvaluatorConfig(type="output", rubric="one"),
            EvaluatorConfig(type="output", rubric="two"),
        ]
    )
    from loom_evals.loader import evaluator_loom_name

    assert [evaluator_loom_name(ev) for ev in built] == ["output", "output_2"]
