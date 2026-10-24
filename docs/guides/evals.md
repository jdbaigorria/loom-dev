# Evaluations

Loom has a built-in evaluation framework that lets you define test cases in YAML, run them against a real agent, and track regressions over time.

## Prerequisites

The recommended install is the evals package itself. `[evals]` on the core is a compatibility alias for the same package.

```bash
pip install loom-declarative-evals
# equivalent: pip install "loom-declarative[evals]"
```

## Setup

### 1. Create the eval file

```bash
loom evals new my_agent
```

Creates `warp/agents/my_agent/evals/evals.yml` with a commented template.

### 2. Define cases and evaluators

```yaml title="warp/agents/my_agent/evals/evals.yml"
cases:
  - name: capital_of_france
    input: "What is the capital of France?"
    expected_output: "Paris"

  - name: order_status
    input: "What is the status of order #12345?"
    expected_output: "The order is shipped"
    expected_trajectory:
      - search_orders     # must use this tool

  - name: greeting
    input: "Hello, how are you?"
    # no expected_output → the evaluator judges quality, not exact match

evaluators:
  - type: output
    rubric: "Is the response accurate, complete, and helpful?"

  - type: trajectory
    rubric: "Did the agent use the right tools in the right order?"
```

### 3. Run

```bash
loom evals run my_agent
```

## Evaluator types

| Type | Description | Fields |
|---|---|---|
| `output` | Evaluates the final answer against a rubric | `rubric`, optional `name` |
| `trajectory` | Evaluates which tools were called and in what order | `rubric`, `trajectory_description`, optional `name` |
| `interactions` | Evaluates the full conversation | `rubric`, `interaction_description`, optional `name` |
| `helpfulness` | Measures how helpful the response is | optional `name` |
| `faithfulness` | Checks factual grounding | optional `name` |
| `goal_success_rate` | Whether the goal was achieved | optional `name` |
| `tool_selection` | Accuracy of tool selection | optional `name` |
| `tool_parameter` | Accuracy of tool parameters | optional `name` |

`name` labels the evaluator in the report. It must be unique inside one `evals.yml`. Omit it and Loom derives a name from `type`, adding `_2`, `_3`, … when the same type appears more than once. On `strands-agents-evals` 1.x the name is also passed to the evaluator constructor so two instances of the same type stay distinct.

### Output evaluator

```yaml
evaluators:
  - type: output
    rubric: "Is the answer factually correct and concise?"
```

### Trajectory evaluator

```yaml
evaluators:
  - type: trajectory
    rubric: "Did the agent follow the expected steps?"
    trajectory_description:
      step_1: "Search the knowledge base"
      step_2: "Synthesize an answer from results"
```

### Helpfulness evaluator

```yaml
evaluators:
  - type: helpfulness
    rubric: "Helpful and actionable?"   # rubric is optional for helpfulness
```

## Commands

```bash
# Run evaluations
loom evals run my_agent
loom evals run my_agent --failures    # show only failing cases
loom evals run my_agent --regression  # compare against previous run

# Inspect history
loom evals compare my_agent           # show all runs from history
loom evals failures my_agent          # last run's failed cases
loom evals regression my_agent        # compare last two runs
loom evals regression my_agent --threshold 0.05  # alert if score drops > 5%
```

## Results storage

Results are saved under `warp/agents/<name>/evals/results/`:
- One JSONL file per run (timestamped)
- Contains per-case scores, rubric justifications, and aggregate metrics

```
warp/agents/my_agent/evals/
├── evals.yml
└── results/
    ├── 2026-06-01T10-00-00.jsonl
    ├── 2026-06-05T14-30-00.jsonl
    └── 2026-06-10T09-15-00.jsonl   ← latest run
```

## Python API

```python
from loom_evals import LoomEvals

evals = LoomEvals("my_agent")
results = evals.run()

for r in results.cases:
    print(r.name, r.score, r.passed)

print(f"Overall: {results.aggregate_score:.2f}")
```

## Regression workflow

```bash
# After a code change, check for regressions:
loom evals run my_agent
loom evals regression my_agent --threshold 0.05

# If regression detected:
# ❌ Regression detected: score dropped from 0.87 to 0.81 (threshold: 0.05)
# Failing cases: capital_of_france, order_status
```

Integrate into CI:

```yaml title=".github/workflows/evals.yml"
- name: Run evaluations
  run: |
    loom evals run my_agent
    loom evals regression my_agent --threshold 0.05
```

!!! note
    Evaluations make real model calls and incur cost. Consider running them on a schedule or pre-merge rather than on every push.
