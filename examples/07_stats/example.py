"""Example 07 — Reading invocation stats.

Each ``run_dev`` call appends a record to ``.loom/stats/{name}.jsonl`` (a dev-only
convenience — in production the backend logs ``response.usage`` itself). Use
``stats_service`` to load and aggregate these records — the same data shown by
``loom agent stats <name>``.

Run:
    python -m examples.07_stats.example
"""

from uuid import uuid4

from loom import LoomSession
from loom.core.paths import build_workspace_paths
from loom.dev import run_dev
from loom.services.stats_service import aggregate, load_stats


def main() -> None:
    session = LoomSession(session_id=str(uuid4()), user_id="user-001")

    # Run the agent a few times to generate stats data.
    questions = [
        "What is 2 + 2?",
        "What is the capital of Germany?",
        "How many days are in a leap year?",
    ]
    for q in questions:
        run = run_dev("assistant", q, session)
        print(f"Q: {q}\nA: {run.response.answer}\n")

    # Load and aggregate the stats.
    stats_file = build_workspace_paths().agent_stats_file("assistant")
    records = load_stats(stats_file)
    summary = aggregate(records)

    print("=== Stats Summary ===")
    print(f"Invocations:       {summary['invocations']}")
    print(f"Total tokens:      {summary['total_tokens']}")
    print(f"Avg input tokens:  {summary['avg_input_tokens']}")
    print(f"Avg output tokens: {summary['avg_output_tokens']}")
    print(f"Avg latency:       {summary['avg_response_time_ms']} ms")
    print(f"Last invocation:   {summary['last_invocation']}")

    if summary.get("top_tools"):
        print("Top tools used:")
        for tool_name, count in summary["top_tools"]:
            print(f"  {tool_name}: {count}x")


if __name__ == "__main__":
    main()
