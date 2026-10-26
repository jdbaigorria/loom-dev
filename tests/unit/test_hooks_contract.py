"""Hook loading contract: HookProvider classes only, replace-merge of defaults, After* semantics."""

import sys
import textwrap

import pytest

from loom.adapters.config import FileConfigSource
from loom.adapters.strands import Agent
from loom.core.exceptions import HookLoadError
from loom.core.loaders.hook import get_hooks
from loom.core.paths import WorkspacePaths
from loom.schemas.config.hook import HookConfig
from loom.testing import MockModel


def _hook(entry) -> list[HookConfig]:
    return [HookConfig.model_validate(entry)]


@pytest.fixture
def hook_module(tmp_path, monkeypatch):
    """An importable module with one provider class and one plain function."""
    (tmp_path / "acme_hooks.py").write_text(
        textwrap.dedent(
            """
            from strands.hooks import AfterInvocationEvent, BeforeInvocationEvent, HookProvider


            class Audit(HookProvider):
                def __init__(self, dest="local"):
                    self.dest = dest
                    self.events = []

                def register_hooks(self, registry, **kwargs):
                    registry.add_callback(BeforeInvocationEvent, lambda e: self.events.append("before"))
                    registry.add_callback(AfterInvocationEvent, self._after)

                def _after(self, event):
                    self.events.append(("after", event.result))


            def record_invocation(*args, **kwargs):
                raise AssertionError("must not be called")
            """
        )
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    yield "acme_hooks"
    sys.modules.pop("acme_hooks", None)


class TestProviderClassOnly:
    @pytest.mark.parametrize("sep", [".", ":"])
    def test_class_by_path_with_params(self, hook_module, sep):
        hooks = get_hooks(_hook({f"{hook_module}{sep}Audit": {"dest": "s3"}}), None)
        assert hooks[0].dest == "s3"

    @pytest.mark.parametrize("sep", [".", ":"])
    def test_function_by_path_is_rejected_without_calling_it(self, hook_module, sep):
        with pytest.raises(HookLoadError, match="not a HookProvider class") as exc:
            get_hooks(_hook(f"{hook_module}{sep}record_invocation"), None)
        assert "function" in str(exc.value.tip)

    def test_local_file_with_function_named_like_the_class(self, tmp_path):
        (tmp_path / "my_hook.py").write_text("def MyHook(*a, **k):\n    raise AssertionError\n")
        with pytest.raises(HookLoadError, match="not a HookProvider class"):
            get_hooks(_hook("my_hook"), tmp_path)

    def test_local_file_with_only_functions(self, tmp_path):
        (tmp_path / "old_style.py").write_text("def before_agent(*a, **k): ...\n")
        with pytest.raises(HookLoadError, match="No HookProvider class found"):
            get_hooks(_hook("old_style"), tmp_path)


class TestAfterInvocationOnFailure:
    def test_after_invocation_runs_with_no_result_when_the_model_raises(self, hook_module):
        class Boom(MockModel):
            async def stream(self, *a, **k):
                raise RuntimeError("model down")
                yield  # pragma: no cover

        (hook,) = get_hooks(_hook(f"{hook_module}:Audit"), None)
        agent = Agent(model=Boom(), hooks=[hook], callback_handler=None)
        with pytest.raises(Exception, match="model down"):
            agent("hi")
        assert hook.events == ["before", ("after", None)]


class TestDefaultsHooksAreReplaced:
    def test_agent_hooks_replace_defaults(self, tmp_path):
        ws = WorkspacePaths(project_root=tmp_path, workspace_name="warp")
        ws.app_dir.mkdir(parents=True, exist_ok=True)
        (ws.app_dir / "app.yml").write_text("defaults:\n  hooks: [logging]\n")
        cfg = ws.agent("a").yaml_file
        cfg.parent.mkdir(parents=True, exist_ok=True)
        cfg.write_text(
            "name: a\nsystem_prompt: {prompt: hi, is_resolved: true}\nhooks: [tool_tracker]\n"
        )
        agent_cfg = FileConfigSource(workspace=ws, env="dev").get_agent_config("a")
        assert [h.name for h in agent_cfg.hooks] == ["tool_tracker"]


class TestGuideExamplesLoad:
    """The classes shown in docs/guides/hooks.md load through the real loader."""

    def test_every_python_example_in_the_guide_loads(self, tmp_path):
        import re
        from pathlib import Path

        guide = Path(__file__).parents[2] / "docs/guides/hooks.md"
        blocks = re.findall(r"```python(?: title=\"([^\"]+)\")?\n(.*?)```", guide.read_text(), re.S)
        assert blocks
        for i, (title, code) in enumerate(blocks):
            fname = Path(title).name if title else f"example_{i}.py"
            (tmp_path / fname).write_text(code)
        names = [p.stem for p in tmp_path.glob("*.py")]
        for name in names:
            assert get_hooks(_hook(name), tmp_path)
