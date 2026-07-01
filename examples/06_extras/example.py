"""Example 06 — Passing extras (caller context) as invocation_state.

Infrastructure context (JWT claims, tenant ID, roles, feature flags) flows from
the caller into the agent's tools as Strands-native ``invocation_state`` — not as
part of the user's message. The backend passes it when it runs the agent
(``agent(query, invocation_state={...})``); in dev, ``run_dev(..., extras=...)``
forwards it for you. Tools read it from their ``ToolContext`` (see
``tools/tenant_tool.py``).

Run:
    python -m examples.06_extras.example
"""

from uuid import uuid4

from loom import LoomSession
from loom.dev import run_dev


def main() -> None:
    session = LoomSession(session_id=str(uuid4()), user_id="user-abc123")

    # Context injected by the backend (e.g. an API Gateway handler), never by the
    # end user. It reaches tools via tool_context.invocation_state.
    run = run_dev(
        "assistant",
        "What tenant am I on and what is my role?",
        session,
        extras={
            "jwt": {"sub": "user-abc123", "email": "alice@example.com", "roles": ["admin"]},
            "tenant_id": "acme-corp",
            "user_role": "admin",
        },
    )

    print(f"Answer: {run.response.answer}")


if __name__ == "__main__":
    main()
