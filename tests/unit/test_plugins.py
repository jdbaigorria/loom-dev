"""Plugins declared in agent YAML build real Strands objects."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from loom.adapters.strands import Agent, AgentSkills, GoalLoop
from loom.core.loaders.plugin import get_plugins
from loom.schemas.config.agent import AgentConfig
from loom.schemas.config.plugin import PluginConfig
from loom.testing import MockModel


def test_skills_plugin_loads_a_skill_file(tmp_path: Path):
    skill = tmp_path / "pdf"
    skill.mkdir()
    (skill / "SKILL.md").write_text("---\nname: pdf\ndescription: Read PDFs\n---\nUse the file.\n", encoding="utf-8")
    built = get_plugins([PluginConfig(name="skills", params={"skills": str(skill)})], None)
    assert isinstance(built[0], AgentSkills)


def test_goal_plugin_accepts_a_natural_language_goal():
    built = get_plugins(
        [PluginConfig(name="goal", params={"goal": "Include the ticket number", "max_attempts": 2})],
        None,
    )
    assert isinstance(built[0], GoalLoop)


def test_agent_receives_the_plugin():
    plugins = get_plugins(
        [PluginConfig(name="goal", params={"goal": "Be brief", "max_attempts": 1})],
        None,
    )
    agent = Agent(model=MockModel(["ok"]), plugins=plugins, callback_handler=None)
    assert "strands:goal-loop" in agent._plugin_registry._plugins


def test_bidi_rejects_plugins():
    with pytest.raises(ValidationError, match="plugins"):
        AgentConfig(name="voice", kind="bidi", plugins=[PluginConfig(name="goal", params={"goal": "x"})])
