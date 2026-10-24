"""Surface tests for the Strands anti-corruption layer (loom.adapters.strands).

These guard the decoupling contract:
- Every symbol the rest of Loom imports from the ACL resolves against the
  installed Strands version (catches upstream module-path moves early, without
  calling an LLM).
- The ``resolve`` helper behaves correctly for fallbacks, submodules, optional
  misses, and hard failures.

If Strands relocates a symbol, exactly one of these tests fails with an
actionable message pointing at ``loom/adapters/strands/`` — instead of an opaque
ImportError surfacing deep inside a loader at runtime.
"""

import pytest

from loom.adapters import strands as sx
from loom.adapters.strands import capabilities
from loom.adapters.strands._resolve import LoomStrandsCompatError, is_available, resolve

# Symbols that may be absent on older Strands (multi-agent primitives and tool
# executors). Their loaders gate on these via capabilities, so None is fine here.
_OPTIONAL = {
    "Swarm",
    "GraphBuilder",
    "MultiAgentResult",
    "ConcurrentToolExecutor",
    "SequentialToolExecutor",
    "StrandsTelemetry",
    "MCPClient",
    "BidiAgent",
    "CedarAuthorization",
}


class TestCoreSurface:
    def test_all_required_symbols_resolve(self):
        missing = [
            name for name in sx.__all__ if name not in _OPTIONAL and getattr(sx, name) is None
        ]
        assert missing == [], f"Unresolved Strands symbols (update the ACL): {missing}"

    def test_optional_symbols_are_class_or_none(self):
        for name in _OPTIONAL:
            value = getattr(sx, name)
            assert value is None or isinstance(value, type)

    def test_export_list_matches_module_attributes(self):
        for name in sx.__all__:
            assert hasattr(sx, name), f"{name} listed in __all__ but missing from module"


class TestResolve:
    def test_returns_first_working_path(self):
        # Second path is bogus; first must win.
        assert resolve("strands.Agent", "strands.nope.Nope") is sx.Agent

    def test_falls_back_to_later_path(self):
        # First path is bogus; resolver must fall through to the valid one.
        assert resolve("strands.nope.Missing", "strands.Agent") is sx.Agent

    def test_resolves_submodule_when_attr_absent(self):
        # tools_use_extractor is a submodule, not an attribute of the package.
        mod = resolve("strands.tools.decorator")
        assert mod is not None

    def test_optional_miss_returns_none(self):
        assert resolve("strands.does.not.Exist", optional=True) is None

    def test_hard_miss_raises_compat_error(self):
        with pytest.raises(LoomStrandsCompatError) as exc:
            resolve("strands.totally.Bogus", "strands.also.Bogus")
        # Error message lists every attempted path for fast diagnosis.
        assert "strands.totally.Bogus" in str(exc.value)
        assert "strands.also.Bogus" in str(exc.value)

    def test_is_available_true_and_false(self):
        assert is_available("strands.Agent") is True
        assert is_available("strands.nope.Nope") is False


class TestCapabilities:
    def test_snapshot_returns_bool_flags(self):
        snap = capabilities.snapshot()
        assert set(snap) == {
            "tool_executor",
            "plugins",
            "a2a",
            "swarm",
            "graph",
            "interrupts",
            "telemetry",
            "mcp",
            "bidi",
            *(f"agent.{name}" for name in capabilities.AGENT_PARAMS),
        }
        assert all(isinstance(v, bool) for v in snap.values())
        assert snap["agent.plugins"] is True
        assert capabilities.agent_accepts("not_a_param") is False


def test_bidi_import_is_not_the_deprecated_path():
    import subprocess
    import sys

    subprocess.check_call(
        [
            sys.executable,
            "-c",
            "import warnings; warnings.simplefilter('error', DeprecationWarning); "
            "import loom.adapters.strands",
        ]
    )
    from loom.adapters.strands import BidiAgent

    assert BidiAgent is not None
    assert not BidiAgent.__module__.startswith("strands.experimental")
