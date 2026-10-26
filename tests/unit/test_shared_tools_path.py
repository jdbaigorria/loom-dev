"""Shared tools dir on sys.path, helper eviction on reload, stable tool module names."""

import sys
import textwrap

import pytest

from loom.core.builder import build_agent
from loom.core.loaders.tool import get_tools
from loom.core.paths import WorkspacePaths
from loom.core.reload import clear_config_caches
from loom.schemas.config.tool import ToolConfig
from loom.schemas.context import LoomSession
from loom.testing import MockModel
from loom.utils import loaders


@pytest.fixture(autouse=True)
def _isolate_sys_state(monkeypatch):
    """Snapshot sys.path / sys.modules / the registered dirs so tests do not leak."""
    monkeypatch.setattr(sys, "path", list(sys.path))
    monkeypatch.setattr(loaders, "_WORKSPACE_PATHS", [])
    before = set(sys.modules)
    yield
    for name in set(sys.modules) - before:
        del sys.modules[name]


@pytest.fixture
def ws(tmp_path) -> WorkspacePaths:
    ws = WorkspacePaths(project_root=tmp_path, workspace_name="warp")
    ws.shared_tools_dir.mkdir(parents=True)
    (ws.shared_tools_dir / "acme").mkdir()
    (ws.shared_tools_dir / "acme" / "__init__.py").write_text("")
    (ws.shared_tools_dir / "acme" / "helper.py").write_text("VALUE = 'one'\n")
    (ws.shared_tools_dir / "probe.py").write_text(
        textwrap.dedent(
            """
            from strands import tool


            @tool
            def probe() -> str:
                \"\"\"Probe.\"\"\"
                from acme.helper import VALUE
                return VALUE
            """
        )
    )
    ws.app_dir.mkdir(parents=True)
    (ws.app_dir / "app.yml").write_text("conversation: none\n")
    cfg = ws.agent("a").yaml_file
    cfg.parent.mkdir(parents=True)
    cfg.write_text(
        "name: a\nconversation: none\nsystem_prompt: {prompt: hi, is_resolved: true}\n"
        "tools: [shared.probe]\n"
    )
    return ws


def _source(ws):
    from loom.adapters.config import FileConfigSource

    return FileConfigSource(workspace=ws, env="dev")


def _build(ws, name="a"):
    return build_agent(name, LoomSession(session_id="s", user_id="u"), source=_source(ws))


@pytest.fixture(autouse=True)
def _mock_model(monkeypatch):
    monkeypatch.setattr("loom.core.builder.get_model", lambda *a, **k: MockModel(["ok"]))


def _probe(agent) -> str:
    return agent.tool.probe()["content"][0]["text"]


def test_tool_imports_helper_package_without_sys_path_hack(ws):
    assert _probe(_build(ws)) == "one"


def test_dir_is_added_once_at_the_end(ws):
    shared = str(ws.shared_tools_dir.resolve())
    for _ in range(3):
        _build(ws)
    assert sys.path.count(shared) == 1
    assert sys.path[-1] == shared


def test_shared_tool_named_json_does_not_shadow_stdlib(ws):
    import json as stdlib_json

    (ws.shared_tools_dir / "json.py").write_text("raise RuntimeError('shadowed')\n")
    _build(ws)
    import json

    assert json is stdlib_json


def test_no_filesystem_source_leaves_sys_path_alone():
    before = list(sys.path)
    from loom.core.builder import build
    from loom.schemas.config.agent import AgentConfig

    build(
        AgentConfig(
            name="a", system_prompt={"prompt": "hi", "is_resolved": True}, conversation="none"
        ),
        LoomSession(session_id="s", user_id="u"),
    )
    assert sys.path == before


def test_editing_helper_is_visible_after_cache_clear(ws):
    assert _probe(_build(ws)) == "one"
    (ws.shared_tools_dir / "acme" / "helper.py").write_text("VALUE = 'second-version'\n")
    clear_config_caches()
    assert _probe(_build(ws)) == "second-version"


def test_local_tools_with_same_name_get_distinct_module_names(tmp_path):
    src = "from strands import tool\n\n@tool\ndef search() -> str:\n    '''s'''\n    return __name__\n"
    dirs = {}
    for agent in ("one", "two"):
        d = tmp_path / agent
        (d / "tools").mkdir(parents=True)
        (d / "tools" / "search.py").write_text(src)
        dirs[agent] = d
    names = {}
    for agent, d in dirs.items():
        (fn,) = get_tools([ToolConfig.model_validate("search")], d, None)
        names[agent] = fn.__module__
    assert names == {
        "one": "loom_workspace.agents.one.search",
        "two": "loom_workspace.agents.two.search",
    }


def test_shared_tool_module_name(ws):
    (fn,) = get_tools([ToolConfig.model_validate("shared.probe")], None, ws.shared_tools_dir)
    assert fn.__module__ == "loom_workspace.shared.probe"
