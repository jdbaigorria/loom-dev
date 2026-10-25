"""
test_config_schemas — Validates that all example agent YAMLs parse correctly
against the AgentConfig schema without any loader mocks.

This guards against schema drift: if a field is renamed or removed in the
schema, a YAML that references the old field name will fail here immediately
instead of silently passing because of an over-mocked test.

Covers IMP-3 from the project audit.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from loom.schemas.config.agent import AgentConfig
from loom.schemas.config.app import AppConfig

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

EXAMPLES_DIR = Path(__file__).parent.parent.parent / "examples"


def _find_agent_yamls() -> list[Path]:
    """Return all *.yml files under examples/ that look like agent configs."""
    return sorted(p for p in EXAMPLES_DIR.rglob("*.yml") if p.name != "app.yml")


def _find_app_yamls() -> list[Path]:
    """Return the app.yml files under examples/."""
    return sorted(EXAMPLES_DIR.rglob("app.yml"))


# ---------------------------------------------------------------------------
# Parametrized: every example YAML must parse as AgentConfig
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "yml_path", _find_agent_yamls(), ids=lambda p: p.relative_to(EXAMPLES_DIR).as_posix()
)
def test_example_yaml_parses_as_agent_config(yml_path: Path) -> None:
    """COV-01: every examples/**/*.yml must be parseable as AgentConfig.

    If a YAML file contains a field that no longer exists in the schema, or is
    missing a required field, this test will fail — catching schema drift early.

    AgentConfig forbids unknown keys, so a typo or a removed field fails here too.
    """
    raw = yaml.safe_load(yml_path.read_text(encoding="utf-8"))
    assert isinstance(raw, dict), f"{yml_path}: expected a YAML mapping, got {type(raw)}"

    # Must not raise
    config = AgentConfig(**raw)

    # Basic sanity: name is always required
    assert config.name, f"{yml_path}: AgentConfig.name is empty"


@pytest.mark.parametrize(
    "yml_path", _find_app_yamls(), ids=lambda p: p.relative_to(EXAMPLES_DIR).as_posix()
)
def test_example_app_yaml_parses_as_app_config(yml_path: Path) -> None:
    """Every examples/**/app.yml must be parseable as AppConfig."""
    raw = yaml.safe_load(yml_path.read_text(encoding="utf-8"))
    assert isinstance(raw, dict), f"{yml_path}: expected a YAML mapping, got {type(raw)}"
    AppConfig(**raw)


# ---------------------------------------------------------------------------
# Unit: AgentConfig required fields and defaults
# ---------------------------------------------------------------------------


class TestAgentConfigDefaults:
    """COV-02: AgentConfig field defaults and required fields."""

    def test_name_is_required(self) -> None:
        """COV-02a: AgentConfig without 'name' raises ValidationError."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            AgentConfig()  # type: ignore[call-arg]

    def test_minimal_config_uses_defaults(self) -> None:
        """COV-02b: Only 'name' required; all other fields use defaults."""
        config = AgentConfig(name="my_agent")

        assert config.description == "Agent created by Loom"
        assert config.retry == "low"
        assert config.output is None
        assert config.tools is None
        assert config.mcp_servers is None
        assert config.hooks is None
        assert config.tool_executor is None

    def test_no_session_field(self) -> None:
        """COV-02c: AgentConfig no longer has 'session' (removed in BUG-2 fix)."""
        assert not hasattr(AgentConfig(name="x"), "session"), (
            "AgentConfig.session was removed; session is app-level config only"
        )

    def test_conversation_defaults_to_none(self) -> None:
        """Per-agent conversation is optional and falls back to app.yml when unset."""
        assert AgentConfig(name="x").conversation is None

    def test_version_is_accepted(self) -> None:
        """The agent template writes version; it is a real field, not an extra key."""
        config = AgentConfig(name="my_agent", version="0.1.0")
        assert config.version == "0.1.0"


# ---------------------------------------------------------------------------
# Unit: AppConfig validates session/conversation at top level
# ---------------------------------------------------------------------------


class TestAppConfigSessionConversation:
    """COV-03: session and conversation are app-level config (BUG-2/BUG-3 guard)."""

    def test_app_config_session_default_is_none(self) -> None:
        """COV-03a: AppConfig.session defaults to None (no persistence — opt-in)."""
        from loom.schemas.config.app import AppConfig

        config = AppConfig(region="us-east-1")
        assert config.session is None

    def test_app_config_session_can_be_set(self) -> None:
        """COV-03b: AppConfig.session can be configured explicitly."""
        from loom.schemas.config.app import AppConfig
        from loom.schemas.config.sessions import FileConfig, FileSession

        config = AppConfig(
            region="us-east-1",
            session=FileSession(provider="file", config=FileConfig(path=".loom/sessions")),
        )
        assert isinstance(config.session, FileSession)

    def test_app_config_conversation_default_is_none_profile(self) -> None:
        """COV-03c: AppConfig.conversation defaults to 'none' profile string."""
        from loom.schemas.config.app import AppConfig

        config = AppConfig(region="us-east-1")
        assert config.conversation == "none"

    def test_app_config_session_from_yaml_dict(self) -> None:
        """COV-03d: session configured via dict (as parsed from app.yml) → FileSession."""
        from loom.schemas.config.app import AppConfig
        from loom.schemas.config.sessions import FileSession

        config = AppConfig.model_validate(
            {
                "region": "us-east-1",
                "session": {"provider": "file", "config": {"path": ".loom/sessions"}},
            }
        )
        assert isinstance(config.session, FileSession)
        assert config.session.config.path == ".loom/sessions"
