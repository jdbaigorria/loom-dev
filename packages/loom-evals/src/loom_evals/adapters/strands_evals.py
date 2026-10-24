"""loom_evals.adapters.strands_evals — Single import surface for ``strands_evals``.

Kept separate from the core ``loom.adapters.strands`` namespace because the
evaluation stack is a distinct dependency (``strands-agents-evals``) with its own
release cadence. Loom's evaluation code imports every ``strands_evals`` symbol
from here.
"""

from __future__ import annotations

from loom.adapters.strands import resolve

# --- Core eval primitives ------------------------------------------------------
Case = resolve("strands_evals.Case", "strands_evals.types.Case")
Experiment = resolve("strands_evals.Experiment", "strands_evals.experiment.Experiment")
Evaluator = resolve("strands_evals.evaluators.Evaluator", "strands_evals.evaluators.base.Evaluator")

# --- Concrete evaluators -------------------------------------------------------
OutputEvaluator = resolve("strands_evals.evaluators.OutputEvaluator")
TrajectoryEvaluator = resolve("strands_evals.evaluators.TrajectoryEvaluator")
InteractionsEvaluator = resolve("strands_evals.evaluators.InteractionsEvaluator")
HelpfulnessEvaluator = resolve("strands_evals.evaluators.HelpfulnessEvaluator")
FaithfulnessEvaluator = resolve("strands_evals.evaluators.FaithfulnessEvaluator")
GoalSuccessRateEvaluator = resolve("strands_evals.evaluators.GoalSuccessRateEvaluator")
ToolSelectionAccuracyEvaluator = resolve("strands_evals.evaluators.ToolSelectionAccuracyEvaluator")
ToolParameterAccuracyEvaluator = resolve("strands_evals.evaluators.ToolParameterAccuracyEvaluator")

# --- Supporting machinery ------------------------------------------------------
tools_use_extractor = resolve("strands_evals.extractors.tools_use_extractor")
StrandsInMemorySessionMapper = resolve("strands_evals.mappers.StrandsInMemorySessionMapper")
StrandsEvalsTelemetry = resolve("strands_evals.telemetry.StrandsEvalsTelemetry")
TaskOutput = resolve("strands_evals.types.TaskOutput")
EvaluationOutput = resolve("strands_evals.types.EvaluationOutput")
EvaluationReport = resolve(
    "strands_evals.types.evaluation_report.EvaluationReport",
    "strands_evals.types.EvaluationReport",
)

__all__ = [
    "Case",
    "EvaluationReport",
    "EvaluationOutput",
    "Evaluator",
    "Experiment",
    "FaithfulnessEvaluator",
    "GoalSuccessRateEvaluator",
    "HelpfulnessEvaluator",
    "InteractionsEvaluator",
    "OutputEvaluator",
    "StrandsEvalsTelemetry",
    "StrandsInMemorySessionMapper",
    "TaskOutput",
    "ToolParameterAccuracyEvaluator",
    "ToolSelectionAccuracyEvaluator",
    "TrajectoryEvaluator",
    "split_reports",
    "tools_use_extractor",
]


def split_reports(result, names: list[str]) -> list[tuple[str, object]]:
    """Normalize ``run_evaluations`` output to ``[(evaluator_name, report), ...]``.

    evals < 0.3 returns one report per evaluator, in ``evaluators`` order.
    evals >= 0.3 returns a single report whose rows carry ``cases[i]["evaluator"]``.
    """
    if isinstance(result, list):
        if len(result) == len(names):
            return list(zip(names, result, strict=True))
        fallback = [
            getattr(report, "evaluator_name", None) or f"evaluator_{index}"
            for index, report in enumerate(result)
        ]
        return list(zip(fallback, result, strict=True))

    cases = list(getattr(result, "cases", None) or [])
    groups: dict[str, list[int]] = {}
    order: list[str] = []
    for index, case in enumerate(cases):
        if isinstance(case, dict):
            evaluator = case.get("evaluator")
        else:
            evaluator = getattr(case, "evaluator", None)
        key = str(evaluator or (names[0] if names else "unknown"))
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append(index)
    if not order:
        key = names[0] if names else "unknown"
        return [(key, result)]

    report_cls = type(result)
    sliced_fields = (
        "scores",
        "test_passes",
        "reasons",
        "detailed_results",
        "cases",
        "diagnoses",
        "recommendations",
    )
    pairs: list[tuple[str, object]] = []
    for evaluator in order:
        indexes = groups[evaluator]
        data: dict = {}
        for field in sliced_fields:
            values = getattr(result, field, None)
            if isinstance(values, list):
                data[field] = [values[i] for i in indexes if i < len(values)]
        scores = data.get("scores") or []
        if hasattr(report_cls, "calculate_overall_score"):
            overall = report_cls.calculate_overall_score(scores)
        else:
            overall = sum(scores) / len(scores) if scores else 0.0
        data["overall_score"] = overall
        fields = getattr(report_cls, "model_fields", {})
        if "evaluator_name" in fields:
            data["evaluator_name"] = evaluator
        sub = report_cls.model_validate(data) if hasattr(report_cls, "model_validate") else report_cls(**data)
        try:
            sub.evaluator_name = evaluator
        except Exception:
            pass
        pairs.append((evaluator, sub))
    return pairs
