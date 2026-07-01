"""Example 02 — Multi-turn conversation (hold a native agent).

Conversation continuity is a property of the live ``strands.Agent``: build it
once with ``loom.build_agent`` and call it across turns — the agent keeps the
message history in memory. (Session persistence is a separate, opt-in concern
configured in ``app.yml``.)

Key rule: one built agent = one conversation. For a new user or conversation,
build a new agent.

Run:
    python -m examples.02_conversation.example
"""

from uuid import uuid4

from loom import LoomSession, build_agent


def main() -> None:
    # Build the agent once; hold it for the whole conversation.
    session = LoomSession(session_id=str(uuid4()), user_id="user-001")
    agent = build_agent("assistant", session)

    conversation = [
        "My name is Alice and I work as a software engineer.",
        "What did I just tell you about myself?",
        "What are common challenges in my profession?",
    ]

    for turn, message in enumerate(conversation, start=1):
        print(f"\n[Turn {turn}] You: {message}")
        result = agent(message)  # native Strands call — history accumulates
        print(f"[Turn {turn}] Agent: {result.message['content'][0]['text']}")

    print(f"\nMessages in history: {len(agent.messages)}")


if __name__ == "__main__":
    main()
