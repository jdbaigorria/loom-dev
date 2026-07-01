"""Example 05 — build_agent() returns a native strands.Agent.

``build_agent(name, session)`` is Loom's core: it resolves the declarative config
and returns a ready ``strands.Agent``. From there you own it — call it, inspect
it, or compose it into a Strands ``Swarm`` / ``GraphBuilder``. Loom does not wrap
or manage execution; that is the caller's (backend's) job.

Use cases:
  - Drive the agent directly with Strands (full control, no Loom indirection)
  - Pass the agent to a Swarm or GraphBuilder node list
  - Inspect ``agent.messages`` / ``agent.model`` / ``agent.tool_names``

Run:
    python -m examples.05_build_and_agent.example
"""

from uuid import uuid4

from loom import LoomSession, build_agent


def main() -> None:
    session = LoomSession(session_id=str(uuid4()), user_id="user-001")

    # Build the native strands.Agent from the declarative config.
    agent = build_agent("assistant", session)
    print(f"Built: {type(agent).__name__}")

    # Drive it natively — Loom is out of the loop from here.
    result = agent("What is 3 + 3?")
    print(f"Answer: {result.message['content'][0]['text']}")

    # Inspect Strands state directly.
    print(f"Messages so far: {len(agent.messages)}")

    # Remember to release MCP connections (if any) when done.
    agent.cleanup()


if __name__ == "__main__":
    main()
