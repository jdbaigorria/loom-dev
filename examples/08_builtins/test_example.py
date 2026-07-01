"""Tests for Example 08 — Built-in tools.

CI-safe: the YAML is parsed and the tools are resolved through the real loader
path; only the network leaves (Bedrock client) are mocked.
"""

from pathlib import Path
from unittest.mock import patch

from loom.core.loaders.agent import get_agent_config
from loom.core.loaders.tool import get_tools

HERE = Path(__file__).parent


def _config():
    return get_agent_config(HERE / "agent.yml")


class TestBuiltinsExample:
    def test_yaml_declara_cuatro_tools_builtin(self):
        """El YAML declara kb + tres apicall (weather, billing, get_invoice domain)."""
        config = _config()
        assert [t.name for t in config.tools] == ["kb", "apicall", "apicall", "apicall"]
        assert all(t.is_builtin for t in config.tools)

    def test_tools_resuelven_con_nombres_strands_correctos(self):
        """get_tools resuelve los builtins a tools Strands bien nombradas."""
        config = _config()
        with patch("boto3.client"):
            tools = get_tools(config.tools, agent_dir=HERE, shared_dir=HERE)
        assert {t.tool_name for t in tools} == {
            "kb_search",
            "weather_api",
            "billing_api",
            "get_invoice",
        }

    def test_apicall_respeta_allowlist_de_la_config(self):
        """La instancia billing_api rechaza paths fuera de su allow-list."""
        config = _config()
        with patch("boto3.client"):
            tools = get_tools(config.tools, agent_dir=HERE, shared_dir=HERE)
        billing = next(t for t in tools if t.tool_name == "billing_api")
        result = billing(path="/v1/secret")  # not in ["/invoices/*", "/customers/*"]
        assert result["status"] == "error"
        assert "not allowed" in result["content"][0]["text"]
