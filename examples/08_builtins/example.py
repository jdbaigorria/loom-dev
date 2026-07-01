"""Example 08 — Built-in tools (``builtin.kb`` + ``builtin.apicall``).

Loom ships two built-in tool *factories* you attach straight from YAML, no
Python required:

  - ``builtin.kb``      — search one or more Amazon Bedrock Knowledge Bases.
  - ``builtin.apicall`` — call a pre-configured HTTP API (with a path allow-list).

You reference them with the ``builtin.`` prefix and configure them via params
(see ``agent.yml``). ``builtin.apicall`` takes a ``name``: it becomes the Strands
tool name, so you can mount several endpoints on one agent without a collision.

This script loads the agent's YAML and resolves its tools **offline** (no LLM
call, no network) to show the concrete Strands tool each builtin produces.

Run:
    python -m examples.08_builtins.example
"""

from pathlib import Path

from loom.core.loaders.agent import get_agent_config
from loom.core.loaders.tool import get_tools

HERE = Path(__file__).parent


def main() -> None:
    config = get_agent_config(HERE / "agent.yml")
    print(f"Agent '{config.name}' declares {len(config.tools)} tool(s):\n")

    # Builtins resolve from loom.builtins, not the filesystem, so the agent/shared
    # dirs are ignored here — any path works.
    tools = get_tools(config.tools, agent_dir=HERE, shared_dir=HERE)

    for tool in tools:
        spec = tool.tool_spec
        params = list(spec["inputSchema"]["json"]["properties"])
        print(f"• {tool.tool_name}")
        print(f"    {spec['description'].strip()[:80]}")
        print(f"    params: {params}\n")

    # Real usage (needs AWS credentials for kb and a reachable API for apicall):
    #
    #     from loom import build_agent, LoomSession
    #
    #     agent = build_agent("support", LoomSession(session_id="s-1", user_id="u-1"))
    #     result = agent("What is our refund policy?")
    #     print(result.message["content"][0]["text"])


if __name__ == "__main__":
    main()
