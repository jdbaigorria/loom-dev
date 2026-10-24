"""Evaluation orchestrator and result analysis for Loom agents.

This module provides the LoomEvals class which orchestrates agent evaluation using
the strands_evals library. It handles the complete evaluation lifecycle:

- **Experiment Loading**: Load evaluation definitions from YAML files
- **Task Execution**: Run agent against test cases, capturing session/trajectory data
- **Result Persistence**: Save evaluation reports in JSON + JSONL formats
- **Regression Detection**: Compare scores across runs to detect performance degradation
- **Failure Analysis**: Extract failed test cases with reasons

Evaluation Architecture:

The LoomEvals.run() method orchestrates:
1. Load experiment (cases + evaluators) from YAML
2. Build task function that:
   - Invokes the agent for each test case
   - Captures session data (if needed for evaluators)
   - Extracts tool trajectories (if needed)
3. Run strands_evals Experiment (parallelized evaluation)
4. Persist results to disk in JSONL format for history tracking
5. Return EvaluationReport objects with per-evaluator scores

Example:
    Evaluate an agent and check for regressions::

        evals = LoomEvals("my_agent")
        reports = evals.run()
        failures = evals.failed_cases(reports)
        regression = evals.check_regression(threshold=0.05)
"""

import json
import logging
from datetime import UTC, datetime

from loom.core.paths import build_workspace_paths
from loom.dev import run_dev
from loom.schemas.context import LoomSession
from loom_evals.adapters.strands_evals import (
    Case,
    EvaluationReport,
    FaithfulnessEvaluator,
    GoalSuccessRateEvaluator,
    HelpfulnessEvaluator,
    InteractionsEvaluator,
    StrandsEvalsTelemetry,
    StrandsInMemorySessionMapper,
    TaskOutput,
    ToolParameterAccuracyEvaluator,
    ToolSelectionAccuracyEvaluator,
    TrajectoryEvaluator,
    tools_use_extractor,
)
from loom_evals.loader import get_experiment

logger = logging.getLogger(__name__)


class LoomEvals:
    """Evaluation orchestrator for Loom agents.

    Manages the complete evaluation lifecycle: loading experiments, running
    agent evaluations, persisting results, and analyzing performance trends.

    Attributes:
        name (str): Name of the agent to evaluate. Must correspond to an
            experiment file at .loom/evals/{name}.yml
    """

    def __init__(self, name: str):
        """Initialize evaluation orchestrator for an agent.

        Args:
            name: Name of the agent (corresponds to experiment filename without .yml).
        """
        self.name = name

    # ------------------------------------------------------------------
    # Run
    # ------------------------------------------------------------------

    def run(self) -> list[EvaluationReport]:
        """Execute the full evaluation pipeline and return all evaluation reports."""
        logger.info("Starting evaluation run for agent '%s'", self.name)
        try:
            experiment = get_experiment(self.name)
            logger.debug(
                "Experiment '%s' loaded with %d case(s) and %d evaluator(s)",
                self.name,
                len(experiment.cases),
                len(experiment.evaluators),
            )

            task_fn = self._build_task_function(experiment.evaluators)
            logger.debug("Task function built for agent '%s'", self.name)

            reports: list[EvaluationReport] = experiment.run_evaluations(task_fn)
            logger.info("Evaluation completed: %d report(s) generated", len(reports))

            self._save_reports(reports)
            logger.info("Evaluation run completed successfully for agent '%s'", self.name)
            return reports
        except Exception as e:
            logger.error(
                "Evaluation run failed for agent '%s': %s", self.name, str(e), exc_info=True
            )
            raise

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _save_reports(self, reports: list):
        """Persist evaluation reports to disk as JSON and JSONL files."""
        try:
            results_dir = build_workspace_paths().eval_results_dir(self.name)
            results_dir.mkdir(parents=True, exist_ok=True)
            logger.debug("Created evaluation results directory: %s", results_dir)

            for report in reports:
                evaluator = report.evaluator_name or "unknown"
                report_file = results_dir / f"{evaluator}.json"
                report.to_file(str(report_file))
                logger.debug("Saved evaluation report for '%s' to %s", evaluator, report_file)

            jsonl_path = results_dir / "results.jsonl"
            with jsonl_path.open("a", encoding="utf-8") as f:
                run_ts = datetime.now(tz=UTC).isoformat()
                for report in reports:
                    record = {
                        "run_ts": run_ts,
                        "experiment": self.name,
                        "agent": self.name,
                        **report.to_dict(),
                    }
                    f.write(json.dumps(record) + "\n")
            logger.info(
                "Evaluation results persisted to %s (%d report(s))", jsonl_path, len(reports)
            )
        except Exception as e:
            logger.error(
                "Failed to save evaluation reports for '%s': %s", self.name, str(e), exc_info=True
            )
            raise

    def history(self) -> list[dict]:
        """Load run history from the JSONL results file."""
        jsonl_path = build_workspace_paths().eval_results_dir(self.name) / "results.jsonl"
        if not jsonl_path.exists():
            logger.debug("No evaluation history found at %s", jsonl_path)
            return []

        records = []
        skipped = 0
        try:
            with jsonl_path.open("r", encoding="utf-8") as f:
                for line_num, line in enumerate(f, start=1):
                    if not line.strip():
                        continue
                    try:
                        record = json.loads(line)
                        records.append(record)
                    except json.JSONDecodeError as e:
                        logger.warning(
                            "Skipped malformed JSON at line %d in %s: %s",
                            line_num,
                            jsonl_path,
                            str(e),
                        )
                        skipped += 1

            if skipped > 0:
                logger.warning(
                    "Loaded %d record(s) from history, skipped %d invalid line(s)",
                    len(records),
                    skipped,
                )
            else:
                logger.debug("Loaded %d record(s) from evaluation history", len(records))
            return records
        except Exception as e:
            logger.error(
                "Failed to load evaluation history from %s: %s", jsonl_path, str(e), exc_info=True
            )
            return []

    # ------------------------------------------------------------------
    # Task function builder
    # ------------------------------------------------------------------

    def _build_task_function(self, evaluators: list):
        """Build a task function compatible with strands_evals based on required evaluator capabilities."""
        needs_session = any(
            isinstance(
                e,
                (
                    HelpfulnessEvaluator,
                    FaithfulnessEvaluator,
                    GoalSuccessRateEvaluator,
                    ToolSelectionAccuracyEvaluator,
                    ToolParameterAccuracyEvaluator,
                    InteractionsEvaluator,
                ),
            )
            for e in evaluators
        )
        needs_trajectory = any(isinstance(e, TrajectoryEvaluator) for e in evaluators)

        logger.debug(
            "Task function flags: needs_session=%s, needs_trajectory=%s",
            needs_session,
            needs_trajectory,
        )

        exporter = None
        if needs_session:
            telemetry = StrandsEvalsTelemetry().setup_in_memory_exporter()
            exporter = telemetry.in_memory_exporter
            logger.debug("In-memory telemetry exporter initialized for session capture")

        def task(case: Case) -> TaskOutput:
            session_id = f"eval-{case.session_id}"
            logger.debug(
                "Executing evaluation case '%s' (session=%s) for agent '%s'",
                case.name or case.input[:50],
                session_id,
                self.name,
            )

            if exporter:
                exporter.clear()

            try:
                run = run_dev(
                    self.name,
                    case.input,
                    LoomSession(session_id=session_id, user_id="eval-runner"),
                )
                output = run.response.answer
                logger.debug(
                    "Case execution completed: tokens=%d, latency=%.0fms",
                    run.response.metadata.total_tokens,
                    run.response.metadata.response_time_ms,
                )

                trajectory = None

                if needs_session and exporter is not None:
                    spans = exporter.get_finished_spans()
                    mapper = StrandsInMemorySessionMapper()
                    trajectory = mapper.map_to_session(spans, session_id=session_id)
                    logger.debug("Session trajectory captured: %d span(s)", len(spans))

                elif needs_trajectory:
                    agent = run.agent
                    assert agent is not None
                    trajectory = tools_use_extractor.extract_agent_tools_used_from_messages(
                        agent.messages
                    )
                    for ev in evaluators:
                        if isinstance(ev, TrajectoryEvaluator):
                            ev.update_trajectory_description(
                                tools_use_extractor.extract_tools_description(agent)
                            )
                    logger.debug("Tool trajectory extracted from agent messages")

                return TaskOutput(output=output, trajectory=trajectory)
            except Exception as e:
                logger.error(
                    "Case execution failed for '%s': %s",
                    case.name or case.input[:50],
                    str(e),
                    exc_info=True,
                )
                raise

        return task

    # ------------------------------------------------------------------
    # Analysis
    # ------------------------------------------------------------------

    def check_regression(self, threshold: float = 0.0) -> dict:
        """Detect performance regressions between last two evaluation runs.

        Compares overall_score for each evaluator between the second-to-last and
        latest evaluation runs. A regression is flagged when score drops by more
        than the specified threshold.

        Args:
            threshold: Maximum allowed score decrease (default: 0.0 = any decrease).
                Example: threshold=0.05 allows up to 5% score decrease without flagging.

        Returns:
            dict: Status with possible values:
                - {"status": "no_history"} - No runs found in history
                - {"status": "single_run"} - Only one run (nothing to compare)
                - {"status": "ok", "regressions": {}} - No regressions detected
                - {"status": "regression", "regressions": {...}} - Regressions found

                regressions dict format:
                {
                    "evaluator_name": {
                        "previous": 0.85,
                        "current": 0.75,
                        "delta": -0.10
                    },
                    ...
                }
        """
        records = self.history()
        if not records:
            return {"status": "no_history"}

        runs: dict[str, list] = {}
        for r in records:
            runs.setdefault(r["run_ts"], []).append(r)

        timestamps = sorted(runs.keys())
        if len(timestamps) < 2:
            return {"status": "single_run"}

        previous = {r["evaluator_name"]: r["overall_score"] for r in runs[timestamps[-2]]}
        current = {r["evaluator_name"]: r["overall_score"] for r in runs[timestamps[-1]]}

        regressions = {}
        for evaluator, curr_score in current.items():
            prev_score = previous.get(evaluator)
            if prev_score is not None:
                delta = curr_score - prev_score
                if delta < -threshold:
                    regressions[evaluator] = {
                        "previous": prev_score,
                        "current": curr_score,
                        "delta": delta,
                    }

        return {
            "status": "regression" if regressions else "ok",
            "regressions": regressions,
        }

    def failed_cases(self, reports: list | None = None) -> list[dict]:
        """Extract failed test cases from evaluation reports.

        Returns a list of cases where test_passes[i] is False, with complete
        context for debugging: evaluator, case name, input, expected output,
        actual output, score, and failure reason.

        Args:
            reports: List of EvaluationReport objects (from run() or direct reports).
                If None, loads from the latest run in history.

        Returns:
            list[dict]: Failed cases with structure:
                [
                    {
                        "evaluator": "output",
                        "case": "greeting_test",
                        "input": "Say hello",
                        "expected": "Hello!",
                        "actual": "Hi there!",
                        "score": 0.6,
                        "reason": "Did not match expected greeting"
                    },
                    ...
                ]
                Returns empty list if no failures or no history.
        """
        if reports is None:
            reports_data = self.history()
            if not reports_data:
                return []
            last_ts = max(r["run_ts"] for r in reports_data)
            reports_data = [r for r in reports_data if r["run_ts"] == last_ts]
        else:
            reports_data = [r.to_dict() for r in reports]

        failures = []
        for report in reports_data:
            evaluator = report.get("evaluator_name", "unknown")
            cases = report.get("cases", [])
            passes = report.get("test_passes", [])
            reasons = report.get("reasons", [])
            scores = report.get("scores", [])

            for i, case in enumerate(cases):
                if i < len(passes) and not passes[i]:
                    failures.append(
                        {
                            "evaluator": evaluator,
                            "case": case.get("name", f"case-{i}"),
                            "score": scores[i] if i < len(scores) else 0.0,
                            "reason": reasons[i] if i < len(reasons) else "",
                            "input": case.get("input"),
                            "expected": case.get("expected_output"),
                            "actual": case.get("actual_output"),
                        }
                    )

        return failures
