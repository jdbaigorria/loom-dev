"""
Bloque 5 — tests/unit/test_core.py

Cubre: loaders.agent.get_agent_config(), loaders.app.get_app_config(),
config/loom_config.get_loom_config(), core/builder.build_agent(),
loaders.app.resolve_env() + load_app_config_with_env() (GAP-02),
builder.build_agent con defaults en AppConfig (GAP-03).
"""

from pathlib import Path

import pytest

from loom.core.paths import WorkspacePaths
from loom.schemas.context import LoomSession

# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def make_loom_env(monkeypatch, tmp_path: Path) -> WorkspacePaths:
    monkeypatch.setenv("LOOM_ROOT", str(tmp_path))
    return WorkspacePaths(project_root=tmp_path, workspace_name="warp")


# ---------------------------------------------------------------------------
# loaders.agent.get_agent_config()
# ---------------------------------------------------------------------------


class TestAgentLoader:
    """COR-A01 a COR-A05"""

    def test_yaml_minimo_retorna_agent_config_correcta(self, monkeypatch, tmp_path):
        """COR-A01: YAML con name y description → AgentConfig con esos valores"""
        make_loom_env(monkeypatch, tmp_path)
        from loom.core.loaders.agent import get_agent_config

        yaml_file = tmp_path / "agent.yml"
        yaml_file.write_text("name: mi_agente\ndescription: Agente de prueba\n", encoding="utf-8")

        result = get_agent_config(yaml_file)

        assert result.name == "mi_agente"
        assert result.description == "Agente de prueba"

    def test_yaml_con_retry_profile_parsea_correctamente(self, monkeypatch, tmp_path):
        """COR-A02: YAML con retry: high → el nombre de profile queda como string"""
        make_loom_env(monkeypatch, tmp_path)
        from loom.core.loaders.agent import get_agent_config

        yaml_file = tmp_path / "retry_agent.yml"
        yaml_file.write_text("name: retry_agent\nretry: high\n", encoding="utf-8")

        result = get_agent_config(yaml_file)

        assert result.retry == "high"

    def test_yaml_sin_campo_name_lanza_validation_error(self, monkeypatch, tmp_path):
        """COR-A03: YAML sin 'name' → ValidationError (campo requerido)"""
        make_loom_env(monkeypatch, tmp_path)
        from pydantic import ValidationError

        from loom.core.loaders.agent import get_agent_config

        yaml_file = tmp_path / "noname_agent.yml"
        yaml_file.write_text("description: sin nombre\n", encoding="utf-8")

        with pytest.raises(ValidationError):
            get_agent_config(yaml_file)

    def test_path_inexistente_lanza_file_not_found(self, monkeypatch, tmp_path):
        """COR-A04: archivo YAML que no existe → FileNotFoundError"""
        make_loom_env(monkeypatch, tmp_path)
        from loom.core.loaders.agent import get_agent_config

        with pytest.raises(FileNotFoundError):
            get_agent_config(tmp_path / "ghost.yml")

    def test_misma_ruta_devuelve_objeto_cacheado(self, monkeypatch, tmp_path):
        """COR-A05: @cache → la misma ruta devuelve el mismo objeto (identidad)"""
        make_loom_env(monkeypatch, tmp_path)
        from loom.core.loaders.agent import get_agent_config

        yaml_file = tmp_path / "cached_agent.yml"
        yaml_file.write_text("name: cached\n", encoding="utf-8")

        result1 = get_agent_config(yaml_file)
        result2 = get_agent_config(yaml_file)

        assert result1 is result2


# ---------------------------------------------------------------------------
# loaders.app.get_app_config()
# ---------------------------------------------------------------------------


class TestAppLoader:
    """COR-B01 a COR-B04"""

    def test_yml_minimo_retorna_defaults_de_app_config(self, monkeypatch, tmp_path):
        """COR-B01: app.yml vacío → AppConfig con valores por defecto"""
        make_loom_env(monkeypatch, tmp_path)
        from loom.core.loaders.app import get_app_config

        app_yml = tmp_path / "app_defaults.yml"
        app_yml.write_text("", encoding="utf-8")

        result = get_app_config(app_yml)

        assert result.region == "us-east-1"
        assert result.log_level == "INFO"

    def test_yml_con_log_level_debug(self, monkeypatch, tmp_path):
        """COR-B02: app.yml con log_level: DEBUG → AppConfig.log_level='DEBUG'"""
        make_loom_env(monkeypatch, tmp_path)
        from loom.core.loaders.app import get_app_config

        app_yml = tmp_path / "app_debug.yml"
        app_yml.write_text("log_level: DEBUG\n", encoding="utf-8")

        result = get_app_config(app_yml)

        assert result.log_level == "DEBUG"

    def test_yml_con_session_file_retorna_file_session(self, monkeypatch, tmp_path):
        """COR-B03: app.yml con session provider=file → AppConfig.session es FileSession"""
        make_loom_env(monkeypatch, tmp_path)
        from loom.core.loaders.app import get_app_config
        from loom.schemas.config.sessions import FileSession

        app_yml = tmp_path / "app_session.yml"
        app_yml.write_text(
            "session:\n  provider: file\n  config:\n    path: .loom/sessions\n",
            encoding="utf-8",
        )

        result = get_app_config(app_yml)

        assert isinstance(result.session, FileSession)
        assert result.session.config.path == ".loom/sessions"

    def test_path_inexistente_lanza_file_not_found(self, monkeypatch, tmp_path):
        """COR-B04: archivo app.yml que no existe → FileNotFoundError"""
        make_loom_env(monkeypatch, tmp_path)
        from loom.core.loaders.app import get_app_config

        with pytest.raises(FileNotFoundError):
            get_app_config(tmp_path / "nope.yml")


# ---------------------------------------------------------------------------
# config/loom_config.get_loom_config()
# ---------------------------------------------------------------------------


class TestLoomConfig:
    """COR-C01 a COR-C04"""

    def test_sin_loom_toml_retorna_config_con_defaults(self, monkeypatch, tmp_path):
        """COR-C01: sin loom.toml → LoomConfig() con valores por defecto"""
        monkeypatch.setenv("LOOM_ROOT", str(tmp_path))
        from loom.config.loom_config import get_loom_config

        result = get_loom_config()

        assert result.workspace_name == "warp"

    def test_loom_toml_con_seccion_workspace_retorna_workspace_name(self, monkeypatch, tmp_path):
        """COR-C02: loom.toml con [workspace] name → workspace_name correcto"""
        monkeypatch.setenv("LOOM_ROOT", str(tmp_path))
        (tmp_path / "loom.toml").write_text(
            '[workspace]\nname = "mi_proyecto"\n',
            encoding="utf-8",
        )
        from loom.config.loom_config import get_loom_config

        result = get_loom_config()

        assert result.workspace_name == "mi_proyecto"

    def test_loom_toml_con_region_legacy_se_ignora_con_warning(self, monkeypatch, tmp_path):
        """COR-C05: 'region' legacy en loom.toml → se ignora (deprecado), no rompe."""
        monkeypatch.setenv("LOOM_ROOT", str(tmp_path))
        (tmp_path / "loom.toml").write_text(
            '[workspace]\nname = "legacy_proj"\nregion = "eu-west-1"\n',
            encoding="utf-8",
        )
        from loom.config.loom_config import get_loom_config

        with pytest.warns(DeprecationWarning, match="region"):
            result = get_loom_config()

        assert result.workspace_name == "legacy_proj"
        assert not hasattr(result, "region")

    def test_loom_toml_invalido_lanza_value_error(self, monkeypatch, tmp_path):
        """COR-C04: loom.toml con TOML inválido → ValueError"""
        monkeypatch.setenv("LOOM_ROOT", str(tmp_path))
        (tmp_path / "loom.toml").write_text("esto = no es : toml valido [[[", encoding="utf-8")
        from loom.config.loom_config import get_loom_config

        with pytest.raises(ValueError, match="Error loading toml config"):
            get_loom_config()


# ---------------------------------------------------------------------------
# core/builder.build_agent()
# ---------------------------------------------------------------------------


class TestBuilder:
    """COR-D01 a COR-D04"""

    @staticmethod
    def _fake_source(mocker, agent_cfg, app_cfg):
        """A fake ConfigSource that serves the given configs (the build() seam)."""
        source = mocker.Mock()
        source.get_agent_config.return_value = agent_cfg
        source.get_app_config.return_value = app_cfg
        return source

    @pytest.fixture
    def builder_env(self, mocker, monkeypatch, tmp_path):
        """
        Mockea todas las dependencias de build_agent para pruebas de cableado puro.
        La config declarativa llega por un ConfigSource inyectado; AppConfig con
        session=None y conversation=None para simplificar el grafo.
        """
        monkeypatch.setenv("LOOM_ROOT", str(tmp_path))

        from loom.schemas.config.agent import AgentConfig
        from loom.schemas.config.app import AppConfig

        agent_cfg = AgentConfig(name="test_agent", description="Agente de test")
        app_cfg = AppConfig(session=None, conversation=None)
        source = self._fake_source(mocker, agent_cfg, app_cfg)

        mocker.patch("loom.core.builder.resolve_env", return_value="dev")
        mocker.patch("loom.core.builder.get_model", return_value=mocker.Mock())
        mocker.patch("loom.core.builder.get_prompt", return_value="system prompt")
        mocker.patch("loom.core.builder.get_retry_strategy", return_value=mocker.Mock())
        mock_agent_cls = mocker.patch("loom.core.builder.Agent")

        return {
            "agent_cfg": agent_cfg,
            "app_cfg": app_cfg,
            "mock_agent_cls": mock_agent_cls,
            "source": source,
        }

    def test_agent_se_crea_con_nombre_y_descripcion_del_yaml(self, builder_env):
        """COR-D01: build_agent → Agent() llamado con name y description correctos"""
        from loom.core.builder import build_agent

        build_agent(
            "test_agent", LoomSession(user_id="u1", session_id="s1"), source=builder_env["source"]
        )

        kwargs = builder_env["mock_agent_cls"].call_args.kwargs
        assert kwargs["name"] == "test_agent"
        assert kwargs["description"] == "Agente de test"

    def test_callback_handler_siempre_es_none(self, builder_env):
        """COR-D02: callback_handler=None siempre se pasa explícitamente a Agent()"""
        from loom.core.builder import build_agent

        build_agent(
            "test_agent", LoomSession(user_id="u1", session_id="s1"), source=builder_env["source"]
        )

        kwargs = builder_env["mock_agent_cls"].call_args.kwargs
        assert kwargs["callback_handler"] is None

    def test_campos_none_se_excluyen_de_params(self, mocker, monkeypatch, tmp_path):
        """COR-D03: session=None, conversation=None, tools=None → no aparecen en Agent()"""
        monkeypatch.setenv("LOOM_ROOT", str(tmp_path))

        from loom.schemas.config.agent import AgentConfig
        from loom.schemas.config.app import AppConfig

        source = self._fake_source(
            mocker,
            AgentConfig(name="minimal"),
            AppConfig(session=None, conversation=None),
        )
        mocker.patch("loom.core.builder.resolve_env", return_value="dev")
        mocker.patch("loom.core.builder.get_model", return_value=mocker.Mock())
        mocker.patch("loom.core.builder.get_prompt", return_value="prompt")
        mocker.patch("loom.core.builder.get_retry_strategy", return_value=mocker.Mock())
        mock_agent_cls = mocker.patch("loom.core.builder.Agent")

        from loom.core.builder import build_agent

        build_agent("minimal", LoomSession(user_id="u1", session_id="s1"), source=source)

        kwargs = mock_agent_cls.call_args.kwargs
        assert "session_manager" not in kwargs
        assert "conversation_manager" not in kwargs
        assert "tools" not in kwargs
        assert "structured_output_model" not in kwargs

    def test_build_agent_retorna_instancia_creada_por_agent(self, builder_env):
        """COR-D04: build_agent retorna el objeto devuelto por Agent()"""
        from loom.core.builder import build_agent

        expected = builder_env["mock_agent_cls"].return_value
        result = build_agent(
            "test_agent", LoomSession(user_id="u1", session_id="s1"), source=builder_env["source"]
        )

        assert result is expected


# ---------------------------------------------------------------------------
# build() engine — resolved-config-in + tools= subset seam (doc §6)
# ---------------------------------------------------------------------------


class TestSelectTools:
    """The per-call tool-subset selector: narrow, don't invent."""

    def test_none_retorna_catalogo_completo(self):
        from loom.core.builder import _select_tools
        from loom.schemas.config.tool import ToolConfig

        defs = [ToolConfig.model_validate("a"), ToolConfig.model_validate("b")]
        assert _select_tools(defs, None) == defs

    def test_subset_recorta_preservando_orden_del_catalogo(self):
        from loom.core.builder import _select_tools
        from loom.schemas.config.tool import ToolConfig

        defs = [ToolConfig.model_validate("a"), ToolConfig.model_validate("b"), ToolConfig.model_validate("c")]
        result = _select_tools(defs, ["c", "a"])
        assert [t.name for t in result] == ["a", "c"]

    def test_tool_desconocida_levanta(self):
        from loom.core.builder import _select_tools
        from loom.core.exceptions import ToolSelectionError
        from loom.schemas.config.tool import ToolConfig

        with pytest.raises(ToolSelectionError):
            _select_tools([ToolConfig.model_validate("a")], ["ghost"])

    def test_catalogo_vacio_con_pedido_levanta(self):
        from loom.core.builder import _select_tools
        from loom.core.exceptions import ToolSelectionError

        with pytest.raises(ToolSelectionError):
            _select_tools(None, ["x"])


class TestBuildEngine:
    """build(agent_config, ...) — assembles from resolved config, no config I/O."""

    @pytest.fixture
    def engine_env(self, mocker, monkeypatch, tmp_path):
        monkeypatch.setenv("LOOM_ROOT", str(tmp_path))
        mocker.patch("loom.core.builder.get_model", return_value=mocker.Mock())
        mocker.patch("loom.core.builder.get_prompt", return_value="system prompt")
        mocker.patch("loom.core.builder.get_retry_strategy", return_value=mocker.Mock())
        get_tools = mocker.patch("loom.core.builder.get_tools", return_value=[])
        mock_agent_cls = mocker.patch("loom.core.builder.Agent")
        return {"get_tools": get_tools, "mock_agent_cls": mock_agent_cls}

    def test_build_usa_config_resuelto_sin_source(self, engine_env):
        """build() recibe un AgentConfig ya resuelto; no necesita ConfigSource."""
        from loom.core.builder import build
        from loom.schemas.config.agent import AgentConfig
        from loom.schemas.config.app import AppConfig

        cfg = AgentConfig(name="eng", description="d")
        build(
            cfg,
            LoomSession(user_id="u", session_id="s"),
            app_config=AppConfig(session=None, conversation=None),
        )

        assert engine_env["mock_agent_cls"].call_args.kwargs["name"] == "eng"

    def test_tools_subset_se_pasa_a_get_tools(self, engine_env):
        from loom.core.builder import build
        from loom.schemas.config.agent import AgentConfig
        from loom.schemas.config.app import AppConfig
        from loom.schemas.config.tool import ToolConfig

        cfg = AgentConfig(name="eng", tools=[ToolConfig.model_validate("a"), ToolConfig.model_validate("b")])
        build(
            cfg,
            LoomSession(user_id="u", session_id="s"),
            app_config=AppConfig(session=None, conversation=None),
            tools=["b"],
        )

        passed = engine_env["get_tools"].call_args.args[0]
        assert [t.name for t in passed] == ["b"]

    def test_tools_subset_desconocido_levanta(self, engine_env):
        from loom.core.builder import build
        from loom.core.exceptions import ToolSelectionError
        from loom.schemas.config.agent import AgentConfig
        from loom.schemas.config.app import AppConfig
        from loom.schemas.config.tool import ToolConfig

        cfg = AgentConfig(name="eng", tools=[ToolConfig.model_validate("a")])
        with pytest.raises(ToolSelectionError):
            build(
                cfg,
                LoomSession(user_id="u", session_id="s"),
                app_config=AppConfig(session=None, conversation=None),
                tools=["ghost"],
            )

    def test_build_sin_paths_con_tool_local_levanta(self, mocker):
        """paths=None (sin filesystem) + tool .py local → error claro (no descubre disco)."""
        from loom.core.builder import build
        from loom.core.exceptions import ToolLoadError
        from loom.schemas.config.agent import AgentConfig
        from loom.schemas.config.app import AppConfig
        from loom.schemas.config.tool import ToolConfig

        mocker.patch("loom.core.builder.get_model", return_value=mocker.Mock())
        mocker.patch("loom.core.builder.Agent")
        cfg = AgentConfig(
            name="x",
            system_prompt={"prompt": "hi", "is_resolved": True},
            tools=[ToolConfig.model_validate("local")],
        )
        with pytest.raises(ToolLoadError, match="no filesystem locator"):
            build(
                cfg,
                LoomSession(user_id="u", session_id="s"),
                app_config=AppConfig(session=None, conversation=None),
            )


# ---------------------------------------------------------------------------
# GAP-02 — loaders.app.resolve_env() + load_app_config_with_env()
# ---------------------------------------------------------------------------


class TestEnvProfiles:
    """COR-E01 a COR-E04"""

    def test_resolve_env_retorna_dev_por_defecto(self, monkeypatch):
        """COR-E01: sin LOOM_ENV → resolve_env() retorna 'dev'"""
        monkeypatch.delenv("LOOM_ENV", raising=False)
        from loom.core.loaders.app import resolve_env

        assert resolve_env() == "dev"

    def test_resolve_env_lee_variable_de_entorno(self, monkeypatch):
        """COR-E02: LOOM_ENV=prod → resolve_env() retorna 'prod'"""
        monkeypatch.setenv("LOOM_ENV", "prod")
        from loom.core.loaders.app import resolve_env

        assert resolve_env() == "prod"

    def test_load_app_config_sin_override_usa_base(self, tmp_path):
        """COR-E03: solo app.yml, sin app.dev.yml → AppConfig de base"""
        from loom.core.loaders.app import load_app_config_with_env

        (tmp_path / "app.yml").write_text("region: eu-west-1\n", encoding="utf-8")

        result = load_app_config_with_env("dev", tmp_path)

        assert result.region == "eu-west-1"

    def test_load_app_config_con_override_mergea_correctamente(self, tmp_path):
        """COR-E04: app.yml + app.prod.yml → override tiene precedencia"""
        from loom.core.loaders.app import load_app_config_with_env

        (tmp_path / "app.yml").write_text("region: us-east-1\nlog_level: INFO\n", encoding="utf-8")
        (tmp_path / "app.prod.yml").write_text("region: eu-west-1\n", encoding="utf-8")

        result = load_app_config_with_env("prod", tmp_path)

        assert result.region == "eu-west-1"  # override
        assert result.log_level == "INFO"  # de base


# ---------------------------------------------------------------------------
# GAP-03 — builder.build_agent con defaults en AppConfig
# ---------------------------------------------------------------------------


class TestBuilderWithDefaults:
    """COR-F01 a COR-F03 — la lógica de merge de defaults vive en FileConfigSource."""

    def test_source_sin_defaults_usa_loader_directo(self, mocker, tmp_path):
        """COR-F01: AppConfig sin defaults → FileConfigSource usa get_agent_config directo"""
        from loom.adapters.config import FileConfigSource
        from loom.schemas.config.agent import AgentConfig
        from loom.schemas.config.app import AppConfig

        ws = WorkspacePaths(project_root=tmp_path, workspace_name="warp")
        src = FileConfigSource(workspace=ws, env="dev")
        mocker.patch.object(
            src, "get_app_config", return_value=AppConfig(session=None, conversation=None, defaults=None)
        )
        # Prompt ya resuelto → la hidratación es no-op y la identidad se preserva.
        agent_cfg = AgentConfig(
            name="my_agent", system_prompt={"prompt": "inline", "is_resolved": True}
        )
        mock_loader = mocker.patch(
            "loom.adapters.config.file_source.get_agent_config", return_value=agent_cfg
        )
        mocker.patch(
            "loom.adapters.config.file_source.resolve_existing_agent_yaml",
            return_value=tmp_path / "a.yml",
        )

        result = src.get_agent_config("my_agent")

        mock_loader.assert_called_once()
        assert result is agent_cfg

    def test_source_con_defaults_mergea_config(self, mocker, tmp_path):
        """COR-F02: defaults en app.yml → AgentConfig toma el default cuando falta en el YAML"""
        from loom.adapters.config import FileConfigSource
        from loom.schemas.config.app import AppConfig

        ws = WorkspacePaths(project_root=tmp_path, workspace_name="warp")
        agent_yaml = ws.agent("minimal_agent").yaml_file
        agent_yaml.parent.mkdir(parents=True, exist_ok=True)
        # Prompt inline para que la hidratación resuelva sin necesitar un prompt.md.
        agent_yaml.write_text(
            "name: minimal_agent\nsystem_prompt: 'You are minimal.'\n", encoding="utf-8"
        )

        src = FileConfigSource(workspace=ws, env="dev")
        mocker.patch.object(
            src,
            "get_app_config",
            return_value=AppConfig(
                session=None,
                conversation=None,
                defaults={"description": "Default description from app.yml"},
            ),
        )

        result = src.get_agent_config("minimal_agent")

        assert result.description == "Default description from app.yml"

    def test_build_agent_con_hooks_pasa_lista_a_agent(self, mocker, monkeypatch, tmp_path):
        """COR-F03: AgentConfig con hooks → get_hooks llamado y 'hooks' en Agent()"""
        monkeypatch.setenv("LOOM_ROOT", str(tmp_path))

        from loom.schemas.config.agent import AgentConfig
        from loom.schemas.config.app import AppConfig
        from loom.schemas.config.hook import HookConfig

        agent_cfg = AgentConfig(
            name="hook_agent",
            hooks=[HookConfig.model_validate("logging")],
        )
        app_cfg = AppConfig(session=None, conversation=None)
        fake_hook = object()

        source = mocker.Mock()
        source.get_agent_config.return_value = agent_cfg
        source.get_app_config.return_value = app_cfg

        mocker.patch("loom.core.builder.resolve_env", return_value="dev")
        mocker.patch("loom.core.builder.get_model", return_value=mocker.Mock())
        mocker.patch("loom.core.builder.get_prompt", return_value="prompt")
        mocker.patch("loom.core.builder.get_retry_strategy", return_value=mocker.Mock())
        mocker.patch("loom.core.builder.get_hooks", return_value=[fake_hook])
        mock_agent_cls = mocker.patch("loom.core.builder.Agent")

        from loom.core.builder import build_agent

        build_agent("hook_agent", LoomSession(user_id="u", session_id="s"), source=source)

        kwargs = mock_agent_cls.call_args.kwargs
        assert "hooks" in kwargs
        assert kwargs["hooks"] == [fake_hook]


# ---------------------------------------------------------------------------
# Tool discriminator — yaml→builtin collapse + FileConfigSource tool hydration
# ---------------------------------------------------------------------------


class TestYamlToolToConfig:
    """yaml_tool_to_config(): un {name}.yaml colapsa a una ToolConfig de builtin."""

    def test_produce_builtin_preservando_nombre_logico(self):
        from loom.core.loaders.tool import yaml_tool_to_config

        cfg = yaml_tool_to_config(
            "get_pokemon", {"builtin": "apicall", "bind": {"base_url": "https://x"}}
        )
        assert cfg.name == "get_pokemon"  # nombre lógico (clave de selección)
        assert cfg.source == "builtin"
        assert cfg.builtin == "apicall"  # registry key separado
        assert cfg.registry_key == "apicall"
        assert "builtin" not in (cfg.params or {})

    def test_sin_builtin_levanta(self):
        from loom.core.exceptions import ToolLoadError
        from loom.core.loaders.tool import yaml_tool_to_config

        with pytest.raises(ToolLoadError, match="must declare 'builtin"):
            yaml_tool_to_config("x", {"bind": {}})

    def test_con_name_levanta(self):
        from loom.core.exceptions import ToolLoadError
        from loom.core.loaders.tool import yaml_tool_to_config

        with pytest.raises(ToolLoadError, match="must not set 'name'"):
            yaml_tool_to_config("x", {"builtin": "apicall", "name": "y"})


class TestFileSourceToolHydration:
    """FileConfigSource resuelve {name}.yaml a builtin; deja .py como código."""

    def _agent_ws(self, tmp_path, *, tools_line: str) -> WorkspacePaths:
        ws = WorkspacePaths(project_root=tmp_path, workspace_name="warp")
        agent = ws.agent("poke")
        agent.config_dir.mkdir(parents=True)
        agent.yaml_file.write_text(
            f"name: poke\nsystem_prompt: 'You help.'\n{tools_line}", encoding="utf-8"
        )
        return ws

    def _src(self, mocker, ws):
        from loom.adapters.config import FileConfigSource
        from loom.schemas.config.app import AppConfig

        src = FileConfigSource(workspace=ws, env="dev")
        mocker.patch.object(
            src, "get_app_config", return_value=AppConfig(session=None, conversation=None, defaults=None)
        )
        return src

    def test_yaml_tool_se_resuelve_a_builtin(self, mocker, tmp_path):
        ws = self._agent_ws(tmp_path, tools_line="tools:\n  - get_pokemon\n")
        tools_dir = ws.agent_dir("poke") / "tools"
        tools_dir.mkdir(parents=True)
        (tools_dir / "get_pokemon.yaml").write_text(
            "builtin: apicall\nbind:\n  base_url: https://x\n", encoding="utf-8"
        )

        cfg = self._src(mocker, ws).get_agent_config("poke")

        tool = cfg.tools[0]
        assert tool.name == "get_pokemon"
        assert tool.source == "builtin"
        assert tool.builtin == "apicall"

    def test_py_tool_pasa_sin_cambios(self, mocker, tmp_path):
        ws = self._agent_ws(tmp_path, tools_line="tools:\n  - my_tool\n")
        tools_dir = ws.agent_dir("poke") / "tools"
        tools_dir.mkdir(parents=True)
        (tools_dir / "my_tool.py").write_text("# code\n", encoding="utf-8")

        cfg = self._src(mocker, ws).get_agent_config("poke")

        tool = cfg.tools[0]
        assert tool.name == "my_tool"
        assert tool.source == "file"
        assert tool.builtin is None

    def test_py_y_yaml_juntos_levanta(self, mocker, tmp_path):
        from loom.core.exceptions import ToolLoadError

        ws = self._agent_ws(tmp_path, tools_line="tools:\n  - dup\n")
        tools_dir = ws.agent_dir("poke") / "tools"
        tools_dir.mkdir(parents=True)
        (tools_dir / "dup.py").write_text("# code\n", encoding="utf-8")
        (tools_dir / "dup.yaml").write_text("builtin: apicall\n", encoding="utf-8")

        with pytest.raises(ToolLoadError, match="both .py and"):
            self._src(mocker, ws).get_agent_config("poke")


# ---------------------------------------------------------------------------
# LoomPaths.agent_dir — path traversal validation (GAP-16)
# ---------------------------------------------------------------------------


class TestLoomPathsAgentDir:
    """COR-P01 a COR-P03"""

    def test_nombre_valido_retorna_path_dentro_de_agents_dir(self, monkeypatch, tmp_path):
        """COR-P01: nombre normal → path bajo agents_dir"""
        monkeypatch.setenv("LOOM_ROOT", str(tmp_path))
        p = WorkspacePaths(project_root=tmp_path, workspace_name="warp")
        result = p.agent_dir("my_agent")
        assert result == p.agents_dir / "my_agent"

    def test_nombre_con_guion_se_normaliza(self, monkeypatch, tmp_path):
        """COR-P02: guiones se convierten a underscores, resultado válido"""
        monkeypatch.setenv("LOOM_ROOT", str(tmp_path))
        p = WorkspacePaths(project_root=tmp_path, workspace_name="warp")
        result = p.agent_dir("my-agent")
        assert result == p.agents_dir / "my_agent"

    def test_path_traversal_lanza_agent_config_error(self, monkeypatch, tmp_path):
        """COR-P03: nombre con '../' → AgentConfigError (path traversal bloqueado)"""
        monkeypatch.setenv("LOOM_ROOT", str(tmp_path))
        from loom.core.exceptions import AgentConfigError

        p = WorkspacePaths(project_root=tmp_path, workspace_name="warp")
        with pytest.raises(AgentConfigError, match="Invalid agent name"):
            p.agent_dir("../../../etc/passwd")


# ---------------------------------------------------------------------------
# LoomPaths — métodos derivados de agent_dir (COR-P04 a COR-P13)
# ---------------------------------------------------------------------------


class TestLoomPathsDerivedPaths:
    """COR-P04 a COR-P13"""

    # --- agent_config_dir ---

    def test_agent_config_dir_es_config_dentro_de_agent_dir(self, monkeypatch, tmp_path):
        """COR-P04: agent_config_dir → <agents_dir>/<name>/config"""
        p = make_loom_env(monkeypatch, tmp_path)
        assert p.agent_config_dir("my_agent") == p.agent_dir("my_agent") / "config"

    def test_agent_config_dir_normaliza_guiones(self, monkeypatch, tmp_path):
        """COR-P05: nombre con guiones → normalizado igual que agent_dir"""
        p = make_loom_env(monkeypatch, tmp_path)
        assert p.agent_config_dir("my-agent") == p.agent_dir("my_agent") / "config"

    def test_agent_config_dir_nombre_invalido_lanza_error(self, monkeypatch, tmp_path):
        """COR-P05b: nombre inválido propaga AgentConfigError desde agent_dir"""
        from loom.core.exceptions import AgentConfigError

        p = make_loom_env(monkeypatch, tmp_path)
        with pytest.raises(AgentConfigError):
            p.agent_config_dir("../evil")

    # --- eval_dir ---

    def test_eval_dir_es_evals_dentro_de_agent_dir(self, monkeypatch, tmp_path):
        """COR-P06: eval_dir → <agents_dir>/<name>/evals"""
        p = make_loom_env(monkeypatch, tmp_path)
        assert p.eval_dir("my_agent") == p.agent_dir("my_agent") / "evals"

    def test_eval_dir_normaliza_guiones(self, monkeypatch, tmp_path):
        """COR-P07: nombre con guiones → normalizado"""
        p = make_loom_env(monkeypatch, tmp_path)
        assert p.eval_dir("my-agent") == p.agent_dir("my_agent") / "evals"

    # --- eval_file ---

    def test_eval_file_es_evals_yml_dentro_de_eval_dir(self, monkeypatch, tmp_path):
        """COR-P08: eval_file → <eval_dir>/evals.yml"""
        p = make_loom_env(monkeypatch, tmp_path)
        assert p.eval_file("my_agent") == p.eval_dir("my_agent") / "evals.yml"

    def test_eval_file_nombre_invalido_lanza_error(self, monkeypatch, tmp_path):
        """COR-P08b: nombre inválido propaga AgentConfigError"""
        from loom.core.exceptions import AgentConfigError

        p = make_loom_env(monkeypatch, tmp_path)
        with pytest.raises(AgentConfigError):
            p.eval_file("../evil")

    # --- agent_prompt_file ---

    def test_agent_prompt_file_es_prompt_md_en_config_dir(self, monkeypatch, tmp_path):
        """COR-P09: agent_prompt_file → <agent_config_dir>/prompt.md"""
        p = make_loom_env(monkeypatch, tmp_path)
        assert p.agent_prompt_file("my_agent") == p.agent_config_dir("my_agent") / "prompt.md"

    # --- agent_prompts_dir ---

    def test_agent_prompts_dir_es_prompts_en_config_dir(self, monkeypatch, tmp_path):
        """COR-P10: agent_prompts_dir → <agent_config_dir>/prompts"""
        p = make_loom_env(monkeypatch, tmp_path)
        assert p.agent_prompts_dir("my_agent") == p.agent_config_dir("my_agent") / "prompts"

    # --- resolve_agent_yaml ---

    def test_resolve_agent_yaml_retorna_path_si_existe(self, monkeypatch, tmp_path):
        """COR-P11: yaml existente → retorna path correcto"""
        p = make_loom_env(monkeypatch, tmp_path)
        yaml_path = p.agent_config_dir("my_agent") / "my_agent.yml"
        yaml_path.parent.mkdir(parents=True, exist_ok=True)
        yaml_path.touch()
        assert p.resolve_agent_yaml("my_agent") == yaml_path

    def test_resolve_agent_yaml_lanza_error_si_no_existe(self, monkeypatch, tmp_path):
        """COR-P12: yaml inexistente → AgentNotFoundError"""
        from loom.core.exceptions import AgentNotFoundError

        p = make_loom_env(monkeypatch, tmp_path)
        with pytest.raises(AgentNotFoundError):
            p.resolve_agent_yaml("ghost_agent")

    def test_resolve_agent_yaml_nombre_invalido_lanza_agent_config_error(
        self, monkeypatch, tmp_path
    ):
        """COR-P13: nombre inválido → AgentConfigError antes de buscar el archivo"""
        from loom.core.exceptions import AgentConfigError

        p = make_loom_env(monkeypatch, tmp_path)
        with pytest.raises(AgentConfigError):
            p.resolve_agent_yaml("../evil")
