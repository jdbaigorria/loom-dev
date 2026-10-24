"""Evaluation experiment loading and configuration transformation.

This module handles loading and transforming evaluation experiments from YAML configuration
into Strands-compatible objects. It manages:

- **Experiment Loading**: Parse YAML files into ExperimentConfig (Pydantic) models
- **Case Transformation**: Convert CaseConfig to strands_evals.Case objects
- **Evaluator Mapping**: Map evaluator type strings to their corresponding Strands classes
- **Field Exclusion**: Handle evaluator-specific field filtering (e.g., rubric handling)

The module implements a type-to-class mapping for 8 evaluator types and ensures proper
field exclusion based on evaluator capabilities. For example:
- Evaluators without rubric support (helpfulness, faithfulness, etc.) exclude the rubric field
- Trajectory-only evaluators exclude interaction_description
- Interaction-only evaluators exclude trajectory_description

Example:
    Load an experiment with mixed evaluator types::

        experiment = get_experiment("my_eval")
        # Now ready for strands_evals.Experiment.run_evaluations(task_fn)
"""

import logging

from loom.core.paths import build_workspace_paths
from loom.utils.loaders import load_config
from loom_evals.adapters.strands_evals import Case, Evaluator, Experiment
from loom_evals.schemas import CaseConfig, EvaluatorConfig, ExperimentConfig

logger = logging.getLogger(__name__)


def _load_experiment(name: str) -> ExperimentConfig:
    """Load and validate experiment configuration from YAML file.

    Loads a YAML experiment file from the evaluation directory and validates it
    against the ExperimentConfig Pydantic schema. This includes validation of
    cases and evaluators list.

    Args:
        name: Name of the experiment (e.g., 'my_eval'). File loaded from
            {workspace}/.loom/evals/{name}.yml

    Returns:
        ExperimentConfig: Validated configuration with parsed cases and evaluators.

    Raises:
        FileNotFoundError: If the experiment YAML file does not exist.
        ValueError: If the YAML is malformed or fails validation.
    """
    experiment_file_path = build_workspace_paths().eval_file(name)
    logger.debug("Loading experiment '%s' from %s", name, experiment_file_path)
    try:
        config = load_config(experiment_file_path)
        experiment_config = ExperimentConfig(**config)
        logger.info(
            "Experiment '%s' loaded: %d case(s), %d evaluator(s)",
            name,
            len(experiment_config.cases),
            len(experiment_config.evaluators),
        )
        return experiment_config
    except FileNotFoundError:
        logger.error("Experiment file not found: %s", experiment_file_path, exc_info=True)
        raise
    except Exception as e:
        logger.error("Failed to load experiment '%s': %s", name, str(e), exc_info=True)
        raise


def get_experiment(name: str) -> Experiment:
    """Load experiment from YAML and convert to Strands-compatible Experiment object.

    This is the primary entry point for loading evaluations. It orchestrates loading
    the configuration, transforming cases and evaluators to Strands types, and
    constructing the final Experiment object ready for evaluation runs.

    The transformation process:
    1. Load YAML config → ExperimentConfig (Pydantic validation)
    2. Transform cases → strands_evals.Case objects
    3. Map evaluators → Strands evaluator instances with proper field handling
    4. Create Experiment(cases, evaluators)

    Args:
        name: Name of the experiment file (without .yml extension).

    Returns:
        Experiment: Strands-compatible Experiment object with:
            - cases: List of Case objects for evaluation
            - evaluators: List of instantiated Evaluator objects

    Raises:
        FileNotFoundError: If experiment file not found.
        ValueError: If configuration invalid or evaluator instantiation fails.

    Example:
        >>> experiment = get_experiment("quality_eval")
        >>> reports = experiment.run_evaluations(task_fn)
    """
    logger.debug("Building Strands Experiment for '%s'", name)
    try:
        config = _load_experiment(name)
        cases = _to_case(config.cases)
        evaluators = _to_evaluator(config.evaluators)
        experiment = Experiment(cases=cases, evaluators=evaluators)
        logger.debug("Experiment ready: %d case(s), %d evaluator(s)", len(cases), len(evaluators))
        return experiment
    except Exception as e:
        logger.error("Failed to build experiment '%s': %s", name, str(e), exc_info=True)
        raise


def _to_case(cases_cfg: list[CaseConfig]) -> list[Case]:
    """Convert Pydantic CaseConfig objects to Strands Case objects.

    Transforms our internal CaseConfig schema (which includes validation and
    defaults) to strands_evals.Case objects. Excludes None values to avoid
    passing unnecessary kwargs.

    Args:
        cases_cfg: List of CaseConfig (Pydantic) objects from experiment YAML.

    Returns:
        list[Case]: List of Strands-compatible Case objects ready for evaluation.
    """
    return [Case(**cfg.model_dump(exclude_none=True)) for cfg in cases_cfg]


def _to_evaluator(evaluators_cfg: list[EvaluatorConfig]) -> list[Evaluator]:
    """Convert EvaluatorConfig objects to instantiated Strands evaluator objects.

    Maps evaluator type strings to their corresponding Strands classes and handles
    field exclusion based on evaluator capabilities:

    - **With Rubric**: output, trajectory, interactions
    - **Without Rubric**: helpfulness, faithfulness, goal_success_rate, tool_selection, tool_parameter

    Field Exclusion Rules:
    - All: Always exclude 'type' field (internal to Loom only)
    - No-Rubric Types: Exclude 'rubric' field (not supported)
    - Non-Trajectory: Exclude 'trajectory_description' field
    - Non-Interactions: Exclude 'interaction_description' field

    Args:
        evaluators_cfg: List of EvaluatorConfig objects from experiment YAML.

    Returns:
        list[Evaluator]: Instantiated Strands evaluator objects.

    Raises:
        TypeError: If evaluator instantiation fails (e.g., missing required params).
        KeyError: If evaluator type is not in the evaluator mapping.
    """
    from loom_evals.adapters.strands_evals import (
        FaithfulnessEvaluator,
        GoalSuccessRateEvaluator,
        HelpfulnessEvaluator,
        InteractionsEvaluator,
        OutputEvaluator,
        ToolParameterAccuracyEvaluator,
        ToolSelectionAccuracyEvaluator,
        TrajectoryEvaluator,
    )

    evaluator_map = {
        "output": OutputEvaluator,
        "trajectory": TrajectoryEvaluator,
        "interactions": InteractionsEvaluator,
        "helpfulness": HelpfulnessEvaluator,
        "faithfulness": FaithfulnessEvaluator,
        "goal_success_rate": GoalSuccessRateEvaluator,
        "tool_selection": ToolSelectionAccuracyEvaluator,
        "tool_parameter": ToolParameterAccuracyEvaluator,
    }

    no_rubric = {
        "helpfulness",
        "faithfulness",
        "goal_success_rate",
        "tool_selection",
        "tool_parameter",
    }

    result = []
    for e in evaluators_cfg:
        cls = evaluator_map[e.type]

        # Always exclude 'type' (not a Strands kwarg)
        exclude = {"type"}

        if e.type in no_rubric:
            exclude.add("rubric")
        if e.type != "trajectory":
            exclude.add("trajectory_description")
        if e.type != "interactions":
            exclude.add("interaction_description")

        kwargs = e.model_dump(exclude=exclude, exclude_none=True)
        try:
            evaluator = cls(**kwargs)
            logger.debug("Evaluator '%s' instantiated (kwargs=%s)", e.type, list(kwargs.keys()))
            result.append(evaluator)
        except TypeError as te:
            logger.error(
                "Failed to instantiate evaluator '%s': %s (kwargs=%s)",
                e.type,
                str(te),
                list(kwargs.keys()),
                exc_info=True,
            )
            raise

    logger.debug("Loaded %d evaluator(s)", len(result))
    return result
