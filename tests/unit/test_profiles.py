"""Tests for the opinionated profiles layer (built-ins + warp/config/profiles.toml)."""

import pytest

from loom.config.profiles import BUILTIN_PROFILES, _merge, get_profiles


class TestMerge:
    def test_user_overrides_builtin_value(self):
        merged = _merge(
            BUILTIN_PROFILES,
            {"retry": {"low": {"max_attempts": 99, "initial_delay": 1, "max_delay": 60}}},
        )
        assert merged["retry"]["low"]["max_attempts"] == 99
        # other built-in profiles are preserved
        assert merged["retry"]["medium"]["max_attempts"] == 4

    def test_user_extends_with_new_profile(self):
        merged = _merge(
            BUILTIN_PROFILES,
            {"model": {"fast": {"import_path": "x.Y", "params": {"model_id": "m"}}}},
        )
        assert "fast" in merged["model"]
        assert "default" in merged["model"]  # built-ins kept


class TestGetProfiles:
    @pytest.fixture(autouse=True)
    def _clear_cache(self):
        get_profiles.cache_clear()
        yield
        get_profiles.cache_clear()

    def test_builtins_when_no_file(self, monkeypatch, tmp_path):
        monkeypatch.setenv("LOOM_ROOT", str(tmp_path))
        profiles = get_profiles()
        assert set(profiles.retry) == {"low", "medium", "high"}
        assert {"default", "economic", "powerful"} <= set(profiles.model)
        assert {"none", "sliding", "summarize"} <= set(profiles.conversation)
        assert profiles.retry["low"].max_attempts == 3
        assert profiles.conversation["summarize"].strategy == "summarizing"
        assert profiles.providers["openai"] == "strands.models.openai.OpenAIModel"
        assert profiles.providers["bedrock"] == "strands.models.bedrock.BedrockModel"

    def test_providers_table_extends_and_overrides_builtins(self, monkeypatch, tmp_path):
        monkeypatch.setenv("LOOM_ROOT", str(tmp_path))
        config_dir = tmp_path / "warp" / "config"
        config_dir.mkdir(parents=True)
        (config_dir / "profiles.toml").write_text(
            '[providers]\nmy_provider = "my.pkg.CustomModel"\nopenai = "my.pkg.PatchedOpenAI"\n'
        )
        profiles = get_profiles()
        assert profiles.providers["my_provider"] == "my.pkg.CustomModel"  # extended
        assert profiles.providers["openai"] == "my.pkg.PatchedOpenAI"  # overridden
        assert "bedrock" in profiles.providers  # built-in still present

    def test_file_overrides_and_extends_builtins(self, monkeypatch, tmp_path):
        monkeypatch.setenv("LOOM_ROOT", str(tmp_path))
        config_dir = tmp_path / "warp" / "config"
        config_dir.mkdir(parents=True)
        (config_dir / "profiles.toml").write_text(
            "[retry.low]\n"
            "max_attempts = 99\n"
            "initial_delay = 1\n"
            "max_delay = 60\n\n"
            "[model.fast]\n"
            'import_path = "strands.models.bedrock.BedrockModel"\n'
            'params = { model_id = "haiku" }\n'
        )
        profiles = get_profiles()
        assert profiles.retry["low"].max_attempts == 99  # overridden
        assert profiles.model["fast"].model_id == "haiku"  # extended
        assert "default" in profiles.model  # built-in still present
