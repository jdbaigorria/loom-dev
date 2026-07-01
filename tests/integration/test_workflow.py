"""
Bloque 7 — tests/integration/test_workflow.py

Tests de integración de punta a punta: init → new agent → list → delete.
Usa filesystem real (tmp_path) sin mocks de servicios.
"""

import pytest

from loom.core.exceptions import ProjectAlreadyInitializedError
from loom.core.paths import WorkspacePaths
from loom.schemas.config.agent import AgentConfig
from loom.schemas.config.app import AppConfig
from loom.services.agent_service import create_agent, delete_agent, get_all_agents
from loom.services.project_service import init_project

# ---------------------------------------------------------------------------
# Fixtures y helpers
# ---------------------------------------------------------------------------


@pytest.fixture
def loom_env(monkeypatch, tmp_path):
    """
    Apunta LOOM_ROOT a tmp_path y crea un ``WorkspacePaths`` para el test.
    Parchea ambos módulos de servicio vía ``build_workspace_paths``.
    """
    monkeypatch.setenv("LOOM_ROOT", str(tmp_path))
    fresh_paths = WorkspacePaths(project_root=tmp_path, workspace_name="warp")
    monkeypatch.setattr(
        "loom.services.project_service.build_workspace_paths", lambda **_: fresh_paths
    )
    monkeypatch.setattr(
        "loom.services.agent_service.build_workspace_paths", lambda **_: fresh_paths
    )
    return tmp_path, fresh_paths


def _app_context() -> dict:
    """Contexto mínimo para init_project, equivalente al que construye el CLI."""
    return {"app": AppConfig().model_dump(exclude_none=True)}


# ---------------------------------------------------------------------------
# INT-01 a INT-08
# ---------------------------------------------------------------------------


class TestIntegrationWorkflow:
    """INT-01 a INT-08"""

    def test_init_crea_estructura_de_carpetas(self, loom_env):
        """INT-01: init_project crea loom.toml, agents/, config/app.yml y .loom/"""
        root, _ = loom_env

        init_project(_app_context())

        assert (root / "loom.toml").is_file()
        assert (root / "warp" / "agents").is_dir()
        assert (root / "warp" / "config" / "app.yml").is_file()
        assert (root / ".loom").is_dir()

    def test_create_agent_crea_archivos_del_agente(self, loom_env):
        """INT-02: create_agent crea __init__.py, tools/, agent.py, config/{name}.yml y prompt.md"""
        root, _ = loom_env
        init_project(_app_context())

        create_agent("my_agent", AgentConfig(name="my_agent"))

        agent_dir = root / "warp" / "agents" / "my_agent"
        assert (agent_dir / "__init__.py").is_file()
        assert (agent_dir / "tools" / "__init__.py").is_file()
        assert (agent_dir / "agent.py").is_file()
        assert (agent_dir / "config" / "my_agent.yml").is_file()
        # AgentConfig default usa system_prompt="prompt.md" → se crea el archivo
        assert (agent_dir / "config" / "prompt.md").is_file()

    def test_get_all_agents_lista_el_agente_creado(self, loom_env):
        """INT-03: get_all_agents() devuelve el agente tras create_agent"""
        _, _ = loom_env
        init_project(_app_context())
        create_agent("my_agent", AgentConfig(name="my_agent"))

        agents = get_all_agents()

        assert len(agents) == 1
        assert agents[0].name == "my_agent"

    def test_delete_agent_elimina_directorio_completo(self, loom_env):
        """INT-04: delete_agent elimina el directorio del agente"""
        root, _ = loom_env
        init_project(_app_context())
        create_agent("my_agent", AgentConfig(name="my_agent"))

        delete_agent("my_agent")

        assert not (root / "warp" / "agents" / "my_agent").exists()

    def test_resolve_agent_yaml_encuentra_yaml_generado(self, loom_env):
        """INT-05: resolve_agent_yaml() encuentra el YAML generado por create_agent"""
        _, fresh_paths = loom_env
        init_project(_app_context())
        create_agent("my_agent", AgentConfig(name="my_agent"))

        yaml_path = fresh_paths.resolve_agent_yaml("my_agent")

        assert yaml_path is not None
        assert yaml_path.exists()
        assert yaml_path.suffix == ".yml"

    def test_segundo_init_sin_force_lanza_error(self, loom_env):
        """INT-06: segunda llamada con force=False levanta ProjectAlreadyInitializedError"""
        _, _ = loom_env
        init_project(_app_context())

        with pytest.raises(ProjectAlreadyInitializedError):
            init_project(_app_context())

    def test_yaml_generado_es_agent_config_valido(self, loom_env):
        """INT-07: el YAML generado por create_agent se puede parsear como AgentConfig válido"""
        _, fresh_paths = loom_env
        from loom.core.loaders.agent import get_agent_config

        init_project(_app_context())
        create_agent("my_agent", AgentConfig(name="my_agent"))

        yaml_path = fresh_paths.resolve_agent_yaml("my_agent")
        config = get_agent_config(yaml_path)

        assert config.name == "my_agent"

    def test_app_yml_generado_es_app_config_valido(self, loom_env):
        """INT-08: el app.yml generado por init_project se puede parsear como AppConfig válido"""
        _, fresh_paths = loom_env
        from loom.core.loaders.app import get_app_config

        init_project(_app_context())

        config = get_app_config(fresh_paths.config_file)

        assert config.region == "us-east-1"
        assert config.log_level == "INFO"
