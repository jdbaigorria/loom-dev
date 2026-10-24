"""Guards for the evals split: the core stays free of evals, and the plugin contract holds."""

import importlib.util
import inspect
import subprocess
import sys


def test_core_import_does_not_load_evals():
    """``import loom`` and the CLI must not pull evals when no plugin is mounted."""
    script = """
import importlib.metadata as md
import sys

_real = md.entry_points

def _hide_loom_plugins(*args, **kwargs):
    if kwargs.get("group") == "loom.cli":
        return md.EntryPoints()
    return _real(*args, **kwargs)

md.entry_points = _hide_loom_plugins

import loom
from loom.cli.cli import app

assert "loom_evals" not in sys.modules
assert "strands_evals" not in sys.modules
assert app is not None
"""
    subprocess.check_call([sys.executable, "-c", script])


def test_plugin_contract_symbols():
    import loom.dev
    import loom.utils.loaders
    import loom.utils.ui
    from loom.adapters.strands import LoomStrandsCompatError, resolve
    from loom.core.exceptions import AgentNotFoundError, LoomError
    from loom.core.paths import WorkspacePaths
    from loom.dev import DevRun, run_dev
    from loom.schemas.context import LoomSession
    from loom.schemas.response import AgentResponse, AgentResponseMetadata

    params = inspect.signature(run_dev).parameters
    assert list(params)[:3] == ["name", "query", "session"]
    for keyword in ("extras", "env", "kind"):
        assert params[keyword].kind is inspect.Parameter.KEYWORD_ONLY
    annotation = inspect.signature(run_dev).return_annotation
    assert annotation is DevRun or annotation == "DevRun"

    assert {"response", "agent"} <= set(DevRun.__dataclass_fields__)
    assert hasattr(AgentResponse, "model_fields") and "answer" in AgentResponse.model_fields
    for field in ("total_tokens", "response_time_ms"):
        assert field in AgentResponseMetadata.model_fields

    for method in ("eval_file", "eval_dir", "eval_results_dir"):
        assert callable(getattr(WorkspacePaths, method))

    assert LoomSession is not None
    assert callable(loom.utils.loaders.load_config)
    assert issubclass(AgentNotFoundError, LoomError)
    for name in ("console", "print_error", "print_hint", "print_success", "print_warning"):
        assert hasattr(loom.utils.ui, name)
    assert callable(resolve)
    assert issubclass(LoomStrandsCompatError, ImportError)
    assert callable(loom.dev.run_dev)
    assert importlib.util.find_spec("loom") is not None
