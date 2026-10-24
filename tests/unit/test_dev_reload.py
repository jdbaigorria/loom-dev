"""Tests for the dev hot-reload machinery (fingerprint + cache invalidation)."""

from pathlib import Path

from loom.cli.commands.dev import _fingerprint
from loom.core.reload import clear_config_caches


class TestFingerprint:
    def test_detects_relevant_files_only(self, tmp_path):
        (tmp_path / "a.yml").write_text("x: 1")
        (tmp_path / "prompt.md").write_text("hi")
        (tmp_path / "tool.py").write_text("x = 1")
        (tmp_path / "ignore.log").write_text("nope")

        fp = _fingerprint([tmp_path])
        names = {Path(p).name for p in fp}
        assert names == {"a.yml", "prompt.md", "tool.py"}  # .log excluded

    def test_changes_when_file_modified(self, tmp_path):
        f = tmp_path / "a.yml"
        f.write_text("x: 1")
        before = _fingerprint([tmp_path])
        # Bump mtime deterministically.
        import os

        os.utime(f, (before[str(f)] + 10, before[str(f)] + 10))
        after = _fingerprint([tmp_path])
        assert after != before

    def test_changes_when_file_added_or_removed(self, tmp_path):
        (tmp_path / "a.yml").write_text("x: 1")
        before = _fingerprint([tmp_path])
        added = tmp_path / "b.yml"
        added.write_text("y: 2")
        assert _fingerprint([tmp_path]) != before
        added.unlink()
        assert _fingerprint([tmp_path]) == before

    def test_recurses_into_subdirs(self, tmp_path):
        sub = tmp_path / "tools"
        sub.mkdir()
        (sub / "t.py").write_text("x = 1")
        fp = _fingerprint([tmp_path])
        assert any(Path(p).as_posix().endswith("tools/t.py") for p in fp)

    def test_missing_dir_is_skipped(self, tmp_path):
        assert _fingerprint([tmp_path / "does_not_exist"]) == {}


class TestClearConfigCaches:
    def test_clears_file_content_cache(self, tmp_path):
        from loom.utils.loaders import _load_file_content, load_file_content

        f = tmp_path / "p.md"
        f.write_text("v1")
        assert load_file_content(f) == "v1"
        assert _load_file_content.cache_info().currsize >= 1

        # Without clearing, the cached read is returned.
        f.write_text("v2")
        assert load_file_content(f) == "v1"

        clear_config_caches()
        assert _load_file_content.cache_info().currsize == 0
        assert load_file_content(f) == "v2"

    def test_clears_all_known_caches_without_error(self):
        # Smoke: every targeted cache exposes cache_clear and is reset.
        from loom.core.loaders.agent import get_agent_config
        from loom.core.loaders.app import get_app_config
        from loom.core.loaders.workflow import get_workflow_config
        from loom.utils.loaders import _load_absolute_config

        clear_config_caches()
        for fn in (get_agent_config, get_app_config, get_workflow_config, _load_absolute_config):
            assert fn.cache_info().currsize == 0
