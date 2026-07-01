"""Tests for the declarative tool_executor strategy (concurrent/sequential)."""

from unittest.mock import patch

import pytest

from loom.adapters.strands import ConcurrentToolExecutor, SequentialToolExecutor
from loom.core.exceptions import AgentConfigError
from loom.core.loaders.tool_executor import get_tool_executor
from loom.schemas.config.agent import AgentConfig


class TestToolExecutorSchema:
    def test_defaults_to_none(self):
        assert AgentConfig(name="a").tool_executor is None

    @pytest.mark.parametrize("value", ["concurrent", "sequential"])
    def test_accepts_valid_strategies(self, value):
        assert AgentConfig(name="a", tool_executor=value).tool_executor == value

    def test_rejects_unknown_strategy(self):
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            AgentConfig(name="a", tool_executor="parallel")


class TestToolExecutorLoader:
    def test_concurrent_builds_concurrent_executor(self):
        assert isinstance(get_tool_executor("concurrent"), ConcurrentToolExecutor)

    def test_sequential_builds_sequential_executor(self):
        assert isinstance(get_tool_executor("sequential"), SequentialToolExecutor)

    def test_missing_strands_capability_raises_friendly_error(self):
        # Simulate an older Strands without pluggable tool executors.
        with patch("loom.core.loaders.tool_executor.sx.ConcurrentToolExecutor", None):
            with pytest.raises(AgentConfigError, match="does not provide pluggable tool executors"):
                get_tool_executor("concurrent")

    def test_capability_check_precedes_strategy_check(self):
        # When unavailable, the error is about the capability, not the strategy.
        with (
            patch("loom.core.loaders.tool_executor.sx.ConcurrentToolExecutor", None),
            patch("loom.core.loaders.tool_executor.sx.SequentialToolExecutor", None),
        ):
            with pytest.raises(AgentConfigError, match="does not provide pluggable"):
                get_tool_executor("concurrent")
