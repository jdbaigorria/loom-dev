from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, model_validator


class CaseConfig(BaseModel):
    name: str
    input: str
    expected_output: str | None = None
    expected_trajectory: list[str] | None = None
    expected_interactions: list[dict[str, str]] | None = None
    expected_environment_state: list[dict[str, str]] | None = None
    metadata: dict[str, str] | None = None

    def validate_for_evaluator(self, evaluator_type: str) -> list[str]:
        warnings: list = []
        required_fields = {
            "output": ["expected_output"],
            "trajectory": ["expected_trajectory"],
            "interactions": ["expected_interactions"],
        }
        for field in required_fields.get(evaluator_type, []):
            if getattr(self, field) is None:
                warnings.append(
                    f"Case '{self.name}' missing '{field}' for {evaluator_type} evaluator"
                )
        return warnings


class EvaluatorConfig(BaseModel):
    type: Literal[
        "output",
        "trajectory",
        "interactions",
        "helpfulness",
        "faithfulness",
        "goal_success_rate",
        "tool_selection",
        "tool_parameter",
    ]
    rubric: str
    interaction_description: dict[str, str] | None = None
    trajectory_description: dict[str, str] | None = None
    model: str | None = None
    system_prompt: str | None = None
    include_inputs: bool = True

    def validate_for_type(self) -> list[str]:
        warnings: list = []
        field_map = {
            "trajectory": {
                "relevant": ["trajectory_description"],
                "irrelevant": ["interaction_description"],
            },
            "interactions": {
                "relevant": ["interaction_description"],
                "irrelevant": ["trajectory_description"],
            },
            "output": {
                "relevant": [],
                "irrelevant": ["trajectory_description", "interaction_description"],
            },
        }
        config = field_map.get(self.type)
        if not config:
            return warnings

        for field in config["relevant"]:
            if getattr(self, field) is None:
                warnings.append(f"Evaluator missing '{field}' (recommended for {self.type})")

        for field in config["irrelevant"]:
            if getattr(self, field) is not None:
                warnings.append(f"Evaluator has '{field}' but {self.type} evaluator ignores it")

        return warnings


class Experiment(BaseModel):
    cases: list[CaseConfig]
    evaluators: list[EvaluatorConfig]


class ExperimentConfig(BaseModel):
    cases: list[CaseConfig]
    evaluators: list[EvaluatorConfig]

    @model_validator(mode="after")
    def cross_validate(self) -> ExperimentConfig:
        """Cross-validate every case against every evaluator at construction time."""
        warnings = []
        for evaluator in self.evaluators:
            warnings.extend(evaluator.validate_for_type())
            for case in self.cases:
                warnings.extend(case.validate_for_evaluator(evaluator.type))

        if warnings:
            import logging

            logger = logging.getLogger("loom.evals")
            for w in warnings:
                logger.warning(w)

        return self
