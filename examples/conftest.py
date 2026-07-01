"""Shared fixtures for Loom examples.

All example tests use ``loom_env`` to run without touching disk or calling
real cloud APIs (Bedrock / OpenAI / Gemini). Loom is a build library now, so the
examples exercise the two sanctioned entry points:

- ``loom.build_agent(name, session)`` → a native ``strands.Agent`` you hold and
  call directly (multi-turn, inspection, composition).
- ``loom.dev.run_dev(name, query, session)`` → the dev-only one-shot executor.

Patch surface:
- ``LOOM_ROOT`` env var → tmp_path
- ``loom.build_agent`` → MagicMock strands.Agent (native examples)
- ``loom.dev.build_dev_agent`` → DevAgent wrapping that mock (run_dev examples)
- ``loom.dev._resolve_kind`` → "agent" (skip filesystem kind probing)
- ``loom.core.response.build_workspace_paths`` → fake workspace (stats path)
"""

from unittest.mock import MagicMock

import pytest

from loom.core.paths import WorkspacePaths


def _make_result(
    answer: str = "Mock response",
    input_tokens: int = 10,
    output_tokens: int = 5,
    latency: float = 100.0,
):
    """Build a fake ``AgentResult`` that mimics what strands returns."""
    result = MagicMock()
    result.message = {"content": [{"text": answer}]}
    result.interrupts = []
    result.metrics.get_summary.return_value = {
        "accumulated_usage": {
            "inputTokens": input_tokens,
            "outputTokens": output_tokens,
            "totalTokens": input_tokens + output_tokens,
        },
        "total_duration": latency,
        "tool_usage": {},
    }
    return result


@pytest.fixture
def make_result():
    """Fixture factory for fake AgentResult — lets tests override answer/tokens."""
    return _make_result


@pytest.fixture
def loom_env(mocker, monkeypatch, tmp_path):
    """Run examples against a mocked agent — no disk, no cloud.

    Exposes:
    - ``loom_env["mock_strands"]`` — the fake ``strands.Agent`` (records messages).
    - ``loom_env["strands_result"][0]`` — the configurable result it returns
      (e.g. ``loom_env["strands_result"][0] = make_result(answer="custom")``).
    - ``loom_env["paths"]`` — the fake workspace (for stats assertions).
    - ``loom_env["mock_build_agent"]`` / ``["mock_build_dev"]`` — the patched builders.
    """
    monkeypatch.setenv("LOOM_ROOT", str(tmp_path))
    fresh_paths = WorkspacePaths(project_root=tmp_path, workspace_name="warp")

    strands_result = [_make_result()]
    mock_strands = MagicMock()
    mock_strands.messages = []
    mock_strands.system_prompt = "mocked prompt"

    def _call(query, *, invocation_state=None, **kwargs):
        answer = strands_result[0].message["content"][0]["text"]
        mock_strands.messages.append({"role": "user", "content": [{"text": str(query)}]})
        mock_strands.messages.append({"role": "assistant", "content": [{"text": answer}]})
        return strands_result[0]

    mock_strands.side_effect = _call

    from loom.dev import DevAgent

    dev_agent = DevAgent(
        agent=mock_strands, model_id="mock-model", system_prompt_tokens=3, name="assistant"
    )

    mock_build_agent = mocker.patch("loom.build_agent", return_value=mock_strands)
    mock_build_dev = mocker.patch("loom.dev.build_dev_agent", return_value=dev_agent)
    mocker.patch("loom.dev._resolve_kind", return_value="agent")
    mocker.patch("loom.core.response.build_workspace_paths", return_value=fresh_paths)

    return {
        "tmp_path": tmp_path,
        "paths": fresh_paths,
        "mock_strands": mock_strands,
        "mock_build_agent": mock_build_agent,
        "mock_build_dev": mock_build_dev,
        "strands_result": strands_result,
    }
