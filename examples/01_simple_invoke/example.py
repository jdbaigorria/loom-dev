"""Example 01 — Simple run (dev executor).

Loom is a build library: it constructs a native ``strands.Agent`` from YAML and
hands it back. For local development and evals, ``loom.dev.run_dev`` is the
dev-only one-shot executor — it builds the agent, runs one turn, records stats,
and tears the agent (and its MCP connections) down.

In production you don't use ``run_dev``: the backend builds the agent with
``loom.build_agent`` and drives it through Strands natively.

Prerequisites:
    - AWS credentials configured (Bedrock)
    - ``assistant.yml`` placed under ``warp/agents/assistant/``
    - Run from the project root (where ``warp/`` and ``.loom/`` live)

Run:
    python -m examples.01_simple_invoke.example
"""

from loom import LoomSession
from loom.dev import run_dev


def main() -> None:
    # Identity for this run (the backend owns id/anon resolution in prod).
    session = LoomSession(session_id="session-001", user_id="user-001")

    # run_dev builds the agent, runs one turn, and shapes the result.
    run = run_dev("assistant", "What is the capital of France?", session)

    print(f"Answer: {run.response.answer}")

    meta = run.response.metadata
    print(f"Tokens: total={meta.total_tokens} (in={meta.input_tokens}, out={meta.output_tokens})")
    print(f"Latency: {meta.response_time_ms:.0f} ms")
    print(f"Model:   {meta.model_id}")
    print(f"Session: {meta.session_id}")

    # In production, skip run_dev — build once and drive Strands natively:
    #
    #     from loom import build_agent, LoomSession
    #     agent = build_agent("assistant", LoomSession(session_id=..., user_id=...))
    #     result = agent("What is the capital of France?")
    #     print(result.message["content"][0]["text"])


if __name__ == "__main__":
    main()
