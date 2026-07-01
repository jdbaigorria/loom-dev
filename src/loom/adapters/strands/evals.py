"""loom.adapters.strands.evals — Single import surface for ``strands_evals``.

Kept separate from the core ``loom.adapters.strands`` namespace because the
evaluation stack is a distinct dependency (``strands-agents-evals``) with its own
release cadence. Loom's evaluation code imports every ``strands_evals`` symbol
from here.
"""

from __future__ import annotations

from ._resolve import resolve

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
EvaluationReport = resolve(
    "strands_evals.types.evaluation_report.EvaluationReport",
    "strands_evals.types.EvaluationReport",
)

__all__ = [
    "Case",
    "EvaluationReport",
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
    "tools_use_extractor",
]
