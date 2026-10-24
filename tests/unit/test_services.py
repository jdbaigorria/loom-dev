"""
Bloque 4 — tests/unit/test_services.py

Cubre: project_service.init_project() y agent_service (get_all_agents,
get_agent_by_name, delete_agent, create_agent, load_agent, validate_agent).
Cubre: project_service.run_doctor() (SVC-DR01 a SVC-DR05).
Cubre: stats_service.load_stats() y stats_service.aggregate() (SVC-SS01 a SVC-SS08).
"""

import textwrap
from pathlib import Path

import pytest

from loom.core.exceptions import (
    AgentAlreadyExistsError,
    AgentInstanceError,
    AgentNotFoundError,
    NoAgentsFoundError,
    ProjectAlreadyInitializedError,
    ProjectNotInitializedError,
)
from loom.core.paths import WorkspacePaths
from loom.schemas.config.agent import AgentConfig

# ---------------------------------------------------------------------------
# Fixture compartida
# ---------------------------------------------------------------------------


@pytest.fixture
def loom_env(monkeypatch, tmp_path):
    """
    Apunta LOOM_ROOT a tmp_path, crea un ``WorkspacePaths`` y lo inyecta
    en ambos módulos de servicio vía ``build_workspace_paths``.
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


# ---------------------------------------------------------------------------
# project_service.init_project()
# ---------------------------------------------------------------------------


class TestProjectService:
    """SVC-P01 a SVC-P05"""

    def _make_context(self) -> dict:
        """Contexto completo (igual al que genera el CLI) para que init renderice."""
        from loom.schemas.config.app import AppConfig

        return {"app": AppConfig().model_dump()}

    def test_init_proyecto_limpio_retorna_lista_de_paths(self, loom_env):
        """SVC-P01: directorio vacío → lista de paths creados no vacía"""
        from loom.services.project_service import init_project

        _, _ = loom_env
        result = init_project(context=self._make_context())

        assert isinstance(result, list)
        assert len(result) > 0
        assert all(isinstance(p, Path) for p in result)

    def test_init_con_loom_toml_existente_sin_force_lanza_error(self, loom_env):
        """SVC-P02: loom.toml ya existe + force=False → ProjectAlreadyInitializedError"""
        from loom.services.project_service import init_project

        tmp_path, fresh_paths = loom_env
        fresh_paths.loom_file.touch()

        with pytest.raises(ProjectAlreadyInitializedError):
            init_project(context=self._make_context())

    def test_init_con_metadata_dir_existente_sin_force_lanza_error(self, loom_env):
        """SVC-P03: .loom/ ya existe + force=False → ProjectAlreadyInitializedError"""
        from loom.services.project_service import init_project

        tmp_path, fresh_paths = loom_env
        fresh_paths.metadata_dir.mkdir(parents=True)

        with pytest.raises(ProjectAlreadyInitializedError):
            init_project(context=self._make_context())

    def test_init_con_force_true_no_lanza_error(self, loom_env):
        """SVC-P04: proyecto ya existe + force=True → no lanza excepción"""
        from loom.services.project_service import init_project

        tmp_path, fresh_paths = loom_env
        fresh_paths.loom_file.touch()

        # No debe lanzar ProjectAlreadyInitializedError
        result = init_project(context=self._make_context(), force=True)
        assert isinstance(result, list)

    def test_init_context_none_falla_porque_el_template_requiere_contexto(self, loom_env):
        """SVC-P05: context=None → {} vacío → el template falla porque 'app' es requerido"""
        from jinja2 import UndefinedError

        from loom.services.project_service import init_project

        # Los templates de init requieren la variable 'app'; con context={} la
        # renderización del nombre de directorio falla con UndefinedError.
        with pytest.raises(UndefinedError):
            init_project(context=None)


# ---------------------------------------------------------------------------
# agent_service.get_all_agents()
# ---------------------------------------------------------------------------


class TestGetAllAgents:
    """SVC-A01 a SVC-A05"""

    def _make_agent_dir(self, fresh_paths: WorkspacePaths, name: str) -> Path:
        """Crea el directorio del agente y retorna su path."""
        agent_dir = fresh_paths.agent_dir(name)
        agent_dir.mkdir(parents=True)
        return agent_dir

    def _make_agent_yaml(
        self, fresh_paths: WorkspacePaths, name: str, content: str | None = None
    ) -> Path:
        """Crea el YAML de config de un agente."""
        self._make_agent_dir(fresh_paths, name)
        config_dir = fresh_paths.agent_config_dir(name)
        config_dir.mkdir(parents=True, exist_ok=True)
        yaml_file = config_dir / f"{name}.yml"
        yaml_file.write_text(
            content or f"name: {name}\ndescription: Test agent\n",
            encoding="utf-8",
        )
        return yaml_file

    def test_agents_dir_no_existe_lanza_error(self, loom_env):
        """SVC-A01: agents_dir no existe → ProjectNotInitializedError"""
        from loom.services.agent_service import get_all_agents

        with pytest.raises(ProjectNotInitializedError):
            get_all_agents()

    def test_agents_dir_vacio_lanza_error(self, loom_env):
        """SVC-A02: agents_dir vacío → NoAgentsFoundError"""
        from loom.services.agent_service import get_all_agents

        _, fresh_paths = loom_env
        fresh_paths.agents_dir.mkdir(parents=True)

        with pytest.raises(NoAgentsFoundError):
            get_all_agents()

    def test_agente_valido_con_yaml_retorna_summary(self, loom_env):
        """SVC-A03: agente con YAML válido → AgentSummary con datos correctos"""
        from loom.services.agent_service import get_all_agents

        _, fresh_paths = loom_env
        self._make_agent_yaml(
            fresh_paths,
            "my_agent",
            "name: my_agent\ndescription: Mi agente\n",
        )

        result = get_all_agents()

        assert len(result) == 1
        assert result[0].name == "my_agent"
        assert result[0].description == "Mi agente"

    def test_agente_con_model_profile_lista_ok(self, loom_env):
        """SVC-A03b (regresión): agente con 'model: <profile>' lista ok, no 'error'.

        El refactor de profiles rompió esto: get_all_agents leía model.provider y
        crasheaba con 'str' object has no attribute 'get' para model: default.
        """
        from loom.services.agent_service import get_all_agents

        _, fresh_paths = loom_env
        self._make_agent_yaml(
            fresh_paths, "prof_agent", "name: prof_agent\ndescription: P\nmodel: default\n"
        )

        result = get_all_agents()

        assert len(result) == 1
        assert result[0].status == "ok"
        assert result[0].model == "default"

    def test_agente_con_model_inline_muestra_model_id(self, loom_env):
        """SVC-A03c: agente con model inline → el descriptor muestra el model_id."""
        from loom.services.agent_service import get_all_agents

        _, fresh_paths = loom_env
        yaml = (
            "name: inline_agent\ndescription: I\n"
            "model:\n  import_path: strands.models.bedrock.BedrockModel\n"
            "  params:\n    model_id: anthropic.claude-x\n"
        )
        self._make_agent_yaml(fresh_paths, "inline_agent", yaml)

        result = get_all_agents()
        assert result[0].status == "ok"
        assert result[0].model == "anthropic.claude-x"

    def test_directorio_tools_se_excluye_de_la_lista(self, loom_env):
        """SVC-A04: carpeta 'tools' en agents_dir no aparece como agente"""
        from loom.services.agent_service import get_all_agents

        _, fresh_paths = loom_env
        # Crear tools/ y un agente real
        tools_dir = fresh_paths.shared_tools_dir
        tools_dir.mkdir(parents=True)
        self._make_agent_yaml(fresh_paths, "real_agent")

        result = get_all_agents()

        names = [a.name for a in result]
        assert "tools" not in names
        assert len(result) == 1

    def test_agente_sin_yaml_retorna_summary_con_missing(self, loom_env):
        """SVC-A05: directorio sin YAML → AgentSummary con filename 'No agent.yml'"""
        from loom.services.agent_service import get_all_agents

        _, fresh_paths = loom_env
        self._make_agent_dir(fresh_paths, "orphan_agent")

        result = get_all_agents()

        assert len(result) == 1
        assert "No orphan_agent.yml" in result[0].filename


# ---------------------------------------------------------------------------
# agent_service.get_agent_by_name()
# ---------------------------------------------------------------------------


class TestGetAgentByName:
    """SVC-A06 a SVC-A08"""

    def test_agente_no_existe_en_disco_lanza_error(self, loom_env):
        """SVC-A06: directorio del agente no existe → NoAgentsFoundError"""
        from loom.services.agent_service import get_agent_by_name

        _, fresh_paths = loom_env
        fresh_paths.agents_dir.mkdir(parents=True)

        with pytest.raises(NoAgentsFoundError):
            get_agent_by_name("ghost_agent")

    def test_agente_existe_sin_yaml_lanza_error(self, loom_env):
        """SVC-A07: directorio existe pero sin YAML → AgentNotFoundError"""
        from loom.services.agent_service import get_agent_by_name

        _, fresh_paths = loom_env
        fresh_paths.agent_dir("no_yaml_agent").mkdir(parents=True)

        with pytest.raises(AgentNotFoundError):
            get_agent_by_name("no_yaml_agent")

    def test_agente_existe_con_yaml_retorna_contenido_y_path(self, loom_env):
        """SVC-A08: agente válido → (content_str, path) con contenido correcto"""
        from loom.services.agent_service import get_agent_by_name

        _, fresh_paths = loom_env
        config_dir = fresh_paths.agent_config_dir("valid_agent")
        config_dir.mkdir(parents=True)
        yaml_file = config_dir / "valid_agent.yml"
        yaml_file.write_text("name: valid_agent\n", encoding="utf-8")

        content, path = get_agent_by_name("valid_agent")

        assert "valid_agent" in content
        assert path == yaml_file


# ---------------------------------------------------------------------------
# agent_service.delete_agent()
# ---------------------------------------------------------------------------


class TestDeleteAgent:
    """SVC-A09 a SVC-A10"""

    def test_delete_agente_no_existente_lanza_error(self, loom_env):
        """SVC-A09: agente no existe → NoAgentsFoundError"""
        from loom.services.agent_service import delete_agent

        _, fresh_paths = loom_env
        fresh_paths.agents_dir.mkdir(parents=True)

        with pytest.raises(NoAgentsFoundError):
            delete_agent("missing_agent")

    def test_delete_agente_existente_elimina_directorio(self, loom_env):
        """SVC-A10: agente existe → su directorio es eliminado"""
        from loom.services.agent_service import delete_agent

        _, fresh_paths = loom_env
        agent_dir = fresh_paths.agent_dir("doomed_agent")
        agent_dir.mkdir(parents=True)
        (agent_dir / "some_file.txt").write_text("contenido")

        delete_agent("doomed_agent")

        assert not agent_dir.exists()


# ---------------------------------------------------------------------------
# agent_service.create_agent()
# ---------------------------------------------------------------------------


class TestCreateAgent:
    """SVC-A11 a SVC-A14"""

    def test_create_sin_proyecto_inicializado_lanza_error(self, loom_env):
        """SVC-A11: agents_dir no existe → ProjectNotInitializedError"""
        from loom.services.agent_service import create_agent

        with pytest.raises(ProjectNotInitializedError):
            create_agent("new_agent", AgentConfig(name="new_agent"))

    def test_create_agente_que_ya_existe_lanza_error(self, loom_env):
        """SVC-A12: directorio del agente ya existe → AgentAlreadyExistsError"""
        from loom.services.agent_service import create_agent

        _, fresh_paths = loom_env
        agent_dir = fresh_paths.agent_dir("existing_agent")
        agent_dir.mkdir(parents=True)

        with pytest.raises(AgentAlreadyExistsError):
            create_agent("existing_agent", AgentConfig(name="existing_agent"))

    def test_create_genera_archivos_del_scaffolding(self, loom_env):
        """SVC-A13: creación válida → lista de paths creados no vacía"""
        from loom.services.agent_service import create_agent

        _, fresh_paths = loom_env
        fresh_paths.agents_dir.mkdir(parents=True)

        result = create_agent("fresh_agent", AgentConfig(name="fresh_agent"))

        assert isinstance(result, list)
        assert len(result) > 0

    def test_create_con_prompt_md_crea_archivo_prompt(self, loom_env):
        """SVC-A14: system_prompt='prompt.md' → se crea config/prompt.md"""
        from loom.services.agent_service import create_agent

        _, fresh_paths = loom_env
        fresh_paths.agents_dir.mkdir(parents=True)

        # AgentConfig usa system_prompt='prompt.md' por defecto
        create_agent("prompt_agent", AgentConfig(name="prompt_agent"))

        prompt_file = fresh_paths.agent_prompt_file("prompt_agent")
        assert prompt_file.exists()

    def test_create_con_prompts_dir_crea_framework_de_seis_archivos(self, loom_env):
        """SVC-A15: system_prompt='prompts' → directorio prompts/ con 6 archivos .md"""
        from loom.schemas.config.prompt import PromptConfig
        from loom.services.agent_service import create_agent

        _, fresh_paths = loom_env
        fresh_paths.agents_dir.mkdir(parents=True)

        config = AgentConfig(
            name="framework_agent",
            system_prompt=PromptConfig(system_prompt="prompts"),
        )
        create_agent("framework_agent", config)

        prompts_dir = fresh_paths.agent_prompts_dir("framework_agent")
        assert prompts_dir.is_dir()
        md_files = list(prompts_dir.glob("*.md"))
        assert len(md_files) == 6


# ---------------------------------------------------------------------------
# agent_service.load_agent()
# ---------------------------------------------------------------------------


class TestLoadAgent:
    """SVC-A16 a SVC-A18"""

    def test_load_sin_agent_py_ni_yaml_lanza_error(self, loom_env):
        """SVC-A16: no hay agent.py ni YAML → AgentNotFoundError"""
        from loom.services.agent_service import load_agent

        _, fresh_paths = loom_env
        # Directorio del agente existe pero está vacío
        fresh_paths.agent_dir("empty_agent").mkdir(parents=True)

        with pytest.raises(AgentNotFoundError):
            load_agent("empty_agent")

    def test_load_agent_py_sin_variable_agent_lanza_error(self, loom_env):
        """SVC-A17: agent.py sin variable 'agent' → AgentInstanceError"""
        from loom.services.agent_service import load_agent

        _, fresh_paths = loom_env
        agent_dir = fresh_paths.agent_dir("bad_py_agent")
        agent_dir.mkdir(parents=True)
        (agent_dir / "agent.py").write_text(
            textwrap.dedent("""
                # No hay variable 'agent' aquí
                def helper():
                    pass
            """),
            encoding="utf-8",
        )

        with pytest.raises(AgentInstanceError):
            load_agent("bad_py_agent")

    def test_load_agent_py_con_variable_retorna_loaded_agent_python(self, loom_env):
        """SVC-A18: agent.py con variable 'agent' → LoadedAgent con source='python'"""
        from loom.services.agent_service import LoadedAgent, load_agent

        _, fresh_paths = loom_env
        agent_dir = fresh_paths.agent_dir("good_py_agent")
        agent_dir.mkdir(parents=True)
        (agent_dir / "agent.py").write_text(
            textwrap.dedent("""
                class _FakeAgent:
                    pass

                agent = _FakeAgent()
            """),
            encoding="utf-8",
        )

        result = load_agent("good_py_agent")

        assert isinstance(result, LoadedAgent)
        assert result.source == "python"
        assert result.instance is not None

    def test_load_sin_agent_py_con_yaml_retorna_loaded_agent_yaml(self, mocker, loom_env):
        """SVC-A19: sin agent.py, YAML válido presente → LoadedAgent con source='yaml', build_agent llamado"""
        from loom.services.agent_service import LoadedAgent, load_agent

        _, fresh_paths = loom_env
        agent_dir = fresh_paths.agent_dir("yaml_agent")
        config_dir = agent_dir / "config"
        config_dir.mkdir(parents=True)
        (config_dir / "yaml_agent.yml").write_text(
            "name: yaml_agent\ndescription: Agente YAML\n", encoding="utf-8"
        )

        mock_agent = mocker.Mock()
        mocker.patch("loom.services.agent_service.build_agent", return_value=mock_agent)

        result = load_agent("yaml_agent")

        assert isinstance(result, LoadedAgent)
        assert result.source == "yaml"
        assert result.instance is mock_agent


# ---------------------------------------------------------------------------
# agent_service.validate_agent()
# ---------------------------------------------------------------------------


class TestValidateAgent:
    """SVC-VA01 a SVC-VA07"""

    def _make_agent_yaml(self, fresh_paths: WorkspacePaths, name: str, content: str) -> Path:
        agent_dir = fresh_paths.agent_dir(name)
        config_dir = agent_dir / "config"
        config_dir.mkdir(parents=True)
        yaml_file = config_dir / f"{name}.yml"
        yaml_file.write_text(content, encoding="utf-8")
        return yaml_file

    def test_agente_no_existe_retorna_error_unico(self, loom_env):
        """SVC-VA01: directorio del agente no existe → lista con 1 resultado ok=False"""
        from loom.services.agent_service import validate_agent

        _, _ = loom_env
        results = validate_agent("fantasma")

        assert len(results) == 1
        assert results[0].ok is False
        assert "not found" in results[0].message
        assert results[0].tip is not None

    def test_yaml_invalido_retorna_error_y_para(self, loom_env):
        """SVC-VA02: YAML inválido según Pydantic → 1 resultado ok=False, para sin más checks"""
        from loom.services.agent_service import validate_agent

        _, fresh_paths = loom_env
        self._make_agent_yaml(
            fresh_paths, "bad_agent", "name: bad_agent\nmodel: {bogus_field: x}\n"
        )

        results = validate_agent("bad_agent")

        assert len(results) == 1
        assert results[0].ok is False
        assert "Invalid YAML" in results[0].message

    def test_yaml_valido_prompt_inline_todos_ok(self, loom_env):
        """SVC-VA03: YAML válido + prompt con texto inline (newline) → todos ok=True"""
        from loom.services.agent_service import validate_agent

        _, fresh_paths = loom_env
        self._make_agent_yaml(
            fresh_paths,
            "inline_agent",
            "name: inline_agent\nsystem_prompt: |-\n  Eres un asistente.\n  Responde siempre en español.\n",
        )

        results = validate_agent("inline_agent")

        assert all(r.ok for r in results)

    def test_yaml_valido_prompt_archivo_existe_ok(self, loom_env):
        """SVC-VA04: YAML con system_prompt='prompt.md', archivo existe → prompt check ok=True"""
        from loom.services.agent_service import validate_agent

        tmp_path, fresh_paths = loom_env
        self._make_agent_yaml(
            fresh_paths,
            "file_agent",
            "name: file_agent\nsystem_prompt: prompt.md\n",
        )
        # validate_agent busca en agent_dir / "config" / source
        (fresh_paths.agent_dir("file_agent") / "config" / "prompt.md").write_text(
            "You are helpful.", encoding="utf-8"
        )

        results = validate_agent("file_agent")

        prompt_result = next(r for r in results if "rompt" in r.message)
        assert prompt_result.ok is True

    def test_yaml_valido_prompt_archivo_faltante_falla(self, loom_env):
        """SVC-VA05: YAML con system_prompt='missing.md', archivo no existe → prompt check ok=False"""
        from loom.services.agent_service import validate_agent

        _, fresh_paths = loom_env
        self._make_agent_yaml(
            fresh_paths,
            "noprompt_agent",
            "name: noprompt_agent\nsystem_prompt: missing_prompt.md\n",
        )

        results = validate_agent("noprompt_agent")

        prompt_result = next(r for r in results if "rompt" in r.message)
        assert prompt_result.ok is False
        assert prompt_result.tip is not None

    def test_tool_local_no_existe_falla(self, loom_env):
        """SVC-VA06: tool local referenciada en YAML no existe en disco → tool check ok=False"""
        from loom.services.agent_service import validate_agent

        tmp_path, fresh_paths = loom_env
        self._make_agent_yaml(
            fresh_paths,
            "tool_agent",
            "name: tool_agent\nsystem_prompt: |-\n  texto inline\ntools:\n  - ghost_tool\n",
        )

        results = validate_agent("tool_agent")

        tool_result = next(r for r in results if "ghost_tool" in r.message)
        assert tool_result.ok is False
        assert tool_result.tip is not None

    def test_tool_local_existe_ok(self, loom_env):
        """SVC-VA07: tool local existe en agent/tools/ → tool check ok=True"""
        from loom.services.agent_service import validate_agent

        _, fresh_paths = loom_env
        self._make_agent_yaml(
            fresh_paths,
            "goodtool_agent",
            "name: goodtool_agent\nsystem_prompt: |-\n  texto inline\ntools:\n  - my_tool\n",
        )
        tools_dir = fresh_paths.agent_dir("goodtool_agent") / "tools"
        tools_dir.mkdir(parents=True)
        (tools_dir / "my_tool.py").write_text("def my_tool(): pass", encoding="utf-8")

        results = validate_agent("goodtool_agent")

        tool_result = next(r for r in results if "my_tool" in r.message)
        assert tool_result.ok is True

    def test_tool_builtin_no_busca_archivo_en_disco(self, loom_env):
        """SVC-VA08: una tool builtin valida contra el registry, no contra un .py.

        Regresión: antes el validador buscaba `tools/apicall.py` y reportaba
        "not found" para un agente que en realidad construye bien.
        """
        from loom.services.agent_service import validate_agent

        _, fresh_paths = loom_env
        self._make_agent_yaml(
            fresh_paths,
            "builtin_agent",
            "name: builtin_agent\nsystem_prompt: |-\n  texto inline\n"
            "tools:\n  - builtin.kb\n  - builtin.apicall\n",
        )

        results = validate_agent("builtin_agent")

        builtin_results = [r for r in results if "Builtin tool" in r.message]
        assert len(builtin_results) == 2
        assert all(r.ok for r in builtin_results)

    def test_tool_builtin_desconocido_falla(self, loom_env):
        """SVC-VA09: un builtin que no está en el registry → ok=False con tip."""
        from loom.services.agent_service import validate_agent

        _, fresh_paths = loom_env
        self._make_agent_yaml(
            fresh_paths,
            "badbuiltin_agent",
            "name: badbuiltin_agent\nsystem_prompt: |-\n  texto inline\ntools:\n  - builtin.nope\n",
        )

        results = validate_agent("badbuiltin_agent")

        tool_result = next(r for r in results if "nope" in r.message)
        assert tool_result.ok is False
        assert tool_result.tip is not None


# ---------------------------------------------------------------------------
# project_service.run_doctor()
# ---------------------------------------------------------------------------


class TestRunDoctor:
    """SVC-DR01 a SVC-DR05"""

    @pytest.fixture
    def doctor_env(self, monkeypatch, tmp_path):
        """
        Entorno mínimo para run_doctor: LOOM_ROOT → tmp_path, ``build_workspace_paths``
        inyectado en project_service y agent_service.
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

    def test_retorna_dict_con_las_cuatro_secciones(self, doctor_env):
        """SVC-DR01: run_doctor(check_aws=False) → dict with keys system/aws/project/agents"""
        from loom.services.project_service import run_doctor

        sections = run_doctor(check_aws=False)

        assert set(sections.keys()) == {"system", "aws", "project", "agents", "plugins"}

    def test_sistema_siempre_incluye_python_y_loom(self, doctor_env):
        """SVC-DR02: system section has at least 2 checks (Python + loom)"""
        from loom.services.project_service import run_doctor

        sections = run_doctor(check_aws=False)

        assert len(sections["system"]) >= 2
        messages = [r.message for r in sections["system"]]
        assert any("Python" in m for m in messages)

    def test_sin_check_aws_seccion_aws_vacia(self, doctor_env):
        """SVC-DR03: check_aws=False → aws section is empty"""
        from loom.services.project_service import run_doctor

        sections = run_doctor(check_aws=False)

        assert sections["aws"] == []

    def test_proyecto_sin_loom_toml_check_falla(self, doctor_env):
        """SVC-DR04: loom.toml not found → project check ok=False with tip"""
        from loom.services.project_service import run_doctor

        sections = run_doctor(check_aws=False)

        toml_result = next(r for r in sections["project"] if "loom.toml" in r.message)
        assert toml_result.ok is False
        assert toml_result.tip is not None

    def test_proyecto_con_loom_toml_check_ok(self, doctor_env):
        """SVC-DR05: loom.toml exists → project check ok=True"""
        from loom.services.project_service import run_doctor

        tmp_path, fresh_paths = doctor_env
        fresh_paths.loom_file.touch()

        sections = run_doctor(check_aws=False)

        toml_result = next(r for r in sections["project"] if "loom.toml" in r.message)
        assert toml_result.ok is True

    def test_sin_agentes_seccion_agentes_vacia(self, doctor_env):
        """SVC-DR06: no initialized project → agents section is empty (no exception raised)"""
        from loom.services.project_service import run_doctor

        sections = run_doctor(check_aws=False)

        assert sections["agents"] == []

    def test_agente_valido_aparece_como_ok(self, doctor_env, mocker):
        """SVC-DR07: agent with all checks OK → row 'name — OK' in agents"""
        from loom.schemas.config.agent_summary import AgentSummary
        from loom.services.agent_service import ValidationResult
        from loom.services.project_service import run_doctor

        tmp_path, fresh_paths = doctor_env
        mocker.patch(
            "loom.services.project_service.get_all_agents",
            return_value=[
                AgentSummary(
                    name="good_agent",
                    description="x",
                    provider="x",
                    model_id="x",
                    filename="good_agent.yml",
                )
            ],
        )
        mocker.patch(
            "loom.services.project_service.validate_agent",
            return_value=[ValidationResult(ok=True, message="YAML schema valid")],
        )

        sections = run_doctor(check_aws=False)

        assert len(sections["agents"]) == 1
        assert sections["agents"][0].ok is True
        assert "good_agent" in sections["agents"][0].message

    def test_python_311_reporta_ok(self, doctor_env, monkeypatch):
        """SVC-DR09: Python 3.11 debe reportar ok=True (BUG-1 fix)"""
        import types

        import loom.services.project_service as svc
        from loom.services.project_service import run_doctor

        # Simula version_info de Python 3.11.0 dentro del módulo
        monkeypatch.setattr(
            svc,
            "sys",
            types.SimpleNamespace(
                version_info=(3, 11, 0, "final", 0),
                version="3.11.0 (default)",
            ),
        )

        sections = run_doctor(check_aws=False)

        python_result = next(r for r in sections["system"] if "Python" in r.message)
        assert python_result.ok is True
        assert python_result.tip is None

    def test_python_310_reporta_falla(self, doctor_env, monkeypatch):
        """SVC-DR10: Python 3.10 (por debajo del mínimo) debe reportar ok=False con tip"""
        import types

        import loom.services.project_service as svc
        from loom.services.project_service import run_doctor

        monkeypatch.setattr(
            svc,
            "sys",
            types.SimpleNamespace(
                version_info=(3, 10, 0, "final", 0),
                version="3.10.0 (default)",
            ),
        )

        sections = run_doctor(check_aws=False)

        python_result = next(r for r in sections["system"] if "Python" in r.message)
        assert python_result.ok is False
        assert python_result.tip is not None
        assert "3.11" in python_result.tip

    def test_agente_con_error_aparece_con_tip(self, doctor_env, mocker):
        """SVC-DR08: agent with a failed check → row with ok=False and validate tip"""
        from loom.schemas.config.agent_summary import AgentSummary
        from loom.services.agent_service import ValidationResult
        from loom.services.project_service import run_doctor

        tmp_path, fresh_paths = doctor_env
        mocker.patch(
            "loom.services.project_service.get_all_agents",
            return_value=[
                AgentSummary(
                    name="broken_agent",
                    description="x",
                    provider="x",
                    model_id="x",
                    filename="broken_agent.yml",
                )
            ],
        )
        mocker.patch(
            "loom.services.project_service.validate_agent",
            return_value=[
                ValidationResult(ok=True, message="YAML schema valid"),
                ValidationResult(ok=False, message="Prompt not found", tip="Create the file"),
            ],
        )

        sections = run_doctor(check_aws=False)

        assert len(sections["agents"]) == 1
        assert sections["agents"][0].ok is False
        assert "broken_agent" in sections["agents"][0].message
        assert sections["agents"][0].tip is not None


# ---------------------------------------------------------------------------
# agent_service.copy_agent()
# ---------------------------------------------------------------------------


class TestCopyAgent:
    """SVC-CP01 a SVC-CP05"""

    def _make_agent(self, fresh_paths: WorkspacePaths, name: str) -> None:
        config_dir = fresh_paths.agent_dir(name) / "config"
        config_dir.mkdir(parents=True)
        (config_dir / f"{name}.yml").write_text(
            f"name: {name}\ndescription: Test\n", encoding="utf-8"
        )

    def test_origen_no_existe_lanza_error(self, loom_env):
        """SVC-CP01: agente origen no existe → AgentNotFoundError"""
        from loom.services.agent_service import copy_agent

        _, fresh_paths = loom_env
        fresh_paths.agents_dir.mkdir(parents=True)

        with pytest.raises(AgentNotFoundError):
            copy_agent("ghost", "new_agent")

    def test_destino_ya_existe_lanza_error(self, loom_env):
        """SVC-CP02: agente destino ya existe → AgentAlreadyExistsError"""
        from loom.services.agent_service import copy_agent

        _, fresh_paths = loom_env
        self._make_agent(fresh_paths, "source")
        self._make_agent(fresh_paths, "dest")

        with pytest.raises(AgentAlreadyExistsError):
            copy_agent("source", "dest")

    def test_copy_exitoso_retorna_lista_de_archivos(self, loom_env):
        """SVC-CP03: copia válida → lista de paths no vacía"""
        from loom.services.agent_service import copy_agent

        _, fresh_paths = loom_env
        self._make_agent(fresh_paths, "original")

        result = copy_agent("original", "clon")

        assert isinstance(result, list)
        assert len(result) > 0

    def test_copy_renombra_yaml_con_nuevo_nombre(self, loom_env):
        """SVC-CP04: YAML en destino tiene el nombre del nuevo agente"""
        from loom.services.agent_service import copy_agent

        _, fresh_paths = loom_env
        self._make_agent(fresh_paths, "src_agent")

        copy_agent("src_agent", "dst_agent")

        new_yaml = fresh_paths.agent_dir("dst_agent") / "config" / "dst_agent.yml"
        assert new_yaml.exists()

    def test_copy_actualiza_campo_name_en_yaml(self, loom_env):
        """SVC-CP05: campo name: en el YAML del nuevo agente refleja el nombre destino"""
        from loom.services.agent_service import copy_agent

        _, fresh_paths = loom_env
        self._make_agent(fresh_paths, "agent_a")

        copy_agent("agent_a", "agent_b")

        new_yaml = fresh_paths.agent_dir("agent_b") / "config" / "agent_b.yml"
        content = new_yaml.read_text(encoding="utf-8")
        assert "name: agent_b" in content
        assert "name: agent_a" not in content


# ---------------------------------------------------------------------------
# validate_agent() — hook checks (GAP-01A)
# ---------------------------------------------------------------------------


class TestValidateAgentHooks:
    """SVC-VH01 a SVC-VH03"""

    def _make_agent_yaml(self, fresh_paths: WorkspacePaths, name: str, content: str) -> None:
        config_dir = fresh_paths.agent_dir(name) / "config"
        config_dir.mkdir(parents=True)
        (config_dir / f"{name}.yml").write_text(content, encoding="utf-8")

    def test_builtin_hook_siempre_ok(self, loom_env):
        """SVC-VH01: hook built-in (logging) → check ok=True sin necesitar archivos"""
        from loom.services.agent_service import validate_agent

        _, fresh_paths = loom_env
        self._make_agent_yaml(
            fresh_paths,
            "hook_agent",
            "name: hook_agent\nsystem_prompt: |-\n  inline\nhooks:\n  - logging\n",
        )

        results = validate_agent("hook_agent")

        hook_result = next(r for r in results if "logging" in r.message and "Hook" in r.message)
        assert hook_result.ok is True

    def test_hook_local_faltante_falla(self, loom_env):
        """SVC-VH02: hook local no encontrado en hooks_dir → check ok=False con tip"""
        from loom.services.agent_service import validate_agent

        _, fresh_paths = loom_env
        self._make_agent_yaml(
            fresh_paths,
            "hook_agent2",
            "name: hook_agent2\nsystem_prompt: |-\n  inline\nhooks:\n  - ghost_hook\n",
        )

        results = validate_agent("hook_agent2")

        hook_result = next(r for r in results if "ghost_hook" in r.message)
        assert hook_result.ok is False
        assert hook_result.tip is not None

    def test_hook_local_existente_ok(self, loom_env):
        """SVC-VH03: hook local existe en hooks_dir → check ok=True"""
        from loom.services.agent_service import validate_agent

        tmp_path, fresh_paths = loom_env
        self._make_agent_yaml(
            fresh_paths,
            "hook_agent3",
            "name: hook_agent3\nsystem_prompt: |-\n  inline\nhooks:\n  - my_validator\n",
        )
        # Crear el archivo del hook local
        fresh_paths.hooks_dir.mkdir(parents=True)
        (fresh_paths.hooks_dir / "my_validator.py").write_text(
            "from strands.hooks import HookProvider, HookRegistry\n"
            "class MyValidator(HookProvider):\n"
            "    def register_hooks(self, registry: HookRegistry, **kwargs): pass\n",
            encoding="utf-8",
        )

        results = validate_agent("hook_agent3")

        hook_result = next(r for r in results if "my_validator" in r.message)
        assert hook_result.ok is True


# ---------------------------------------------------------------------------
# stats_service.load_stats() y aggregate()
# ---------------------------------------------------------------------------


class TestStatsService:
    """SVC-SS01 a SVC-SS08"""

    def _write_jsonl(self, path: Path, records: list[dict]) -> None:
        import json

        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(json.dumps(r) for r in records), encoding="utf-8")

    def test_load_stats_sin_archivo_retorna_lista_vacia(self, tmp_path):
        """SVC-SS01: archivo inexistente → lista vacía"""
        from loom.services.stats_service import load_stats

        result = load_stats(tmp_path / "nope.jsonl")
        assert result == []

    def test_load_stats_archivo_vacio_retorna_lista_vacia(self, tmp_path):
        """SVC-SS02: archivo vacío → lista vacía"""
        from loom.services.stats_service import load_stats

        f = tmp_path / "agent.jsonl"
        f.write_text("", encoding="utf-8")
        assert load_stats(f) == []

    def test_load_stats_linea_invalida_se_omite(self, tmp_path):
        """SVC-SS03: línea con JSON inválido se omite sin excepción"""
        import json

        from loom.services.stats_service import load_stats

        f = tmp_path / "agent.jsonl"
        f.write_text(
            "not-json\n" + json.dumps({"ts": "x", "input_tokens": 1}) + "\n", encoding="utf-8"
        )
        result = load_stats(f)
        assert len(result) == 1
        assert result[0]["input_tokens"] == 1

    def test_load_stats_retorna_todos_los_registros(self, tmp_path):
        """SVC-SS04: JSONL con 3 líneas → lista con 3 dicts"""
        from loom.services.stats_service import load_stats

        records = [{"ts": f"t{i}", "input_tokens": i} for i in range(3)]
        f = tmp_path / "agent.jsonl"
        self._write_jsonl(f, records)
        assert len(load_stats(f)) == 3

    def test_aggregate_sin_registros_retorna_cero_invocations(self):
        """SVC-SS05: lista vacía → {"invocations": 0}"""
        from loom.services.stats_service import aggregate

        assert aggregate([]) == {"invocations": 0}

    def test_aggregate_un_registro_calcula_correctamente(self):
        """SVC-SS06: un registro → campos calculados correctamente"""
        from loom.services.stats_service import aggregate

        records = [
            {
                "ts": "2026-03-21T10:00:00+00:00",
                "input_tokens": 100,
                "output_tokens": 50,
                "total_tokens": 150,
                "response_time_ms": 300.0,
                "tool_calls": [],
                "system_prompt_tokens": 200,
            }
        ]
        result = aggregate(records)
        assert result["invocations"] == 1
        assert result["total_tokens"] == 150
        assert result["avg_input_tokens"] == 100
        assert result["avg_response_time_ms"] == 300.0
        assert result["system_prompt_tokens"] == 200

    def test_aggregate_multiples_registros_suma_y_promedia(self):
        """SVC-SS07: dos registros → tokens sumados, promedios correctos"""
        from loom.services.stats_service import aggregate

        records = [
            {
                "ts": "2026-03-21T10:00:00+00:00",
                "input_tokens": 100,
                "output_tokens": 50,
                "total_tokens": 150,
                "response_time_ms": 200.0,
                "tool_calls": ["search"],
                "system_prompt_tokens": 100,
            },
            {
                "ts": "2026-03-21T11:00:00+00:00",
                "input_tokens": 200,
                "output_tokens": 100,
                "total_tokens": 300,
                "response_time_ms": 400.0,
                "tool_calls": ["search", "db"],
                "system_prompt_tokens": 100,
            },
        ]
        result = aggregate(records)
        assert result["invocations"] == 2
        assert result["total_tokens"] == 450
        assert result["avg_input_tokens"] == 150
        assert result["avg_response_time_ms"] == 300.0
        assert result["top_tools"][0] == ("search", 2)

    def test_aggregate_last_invocation_es_el_ts_mas_reciente(self):
        """SVC-SS08: last_invocation apunta al registro con ts más alto"""
        from loom.services.stats_service import aggregate

        records = [
            {
                "ts": "2026-03-21T09:00:00+00:00",
                "input_tokens": 10,
                "output_tokens": 5,
                "total_tokens": 15,
                "response_time_ms": 100.0,
                "tool_calls": [],
                "system_prompt_tokens": 0,
            },
            {
                "ts": "2026-03-21T12:00:00+00:00",
                "input_tokens": 20,
                "output_tokens": 10,
                "total_tokens": 30,
                "response_time_ms": 200.0,
                "tool_calls": [],
                "system_prompt_tokens": 50,
            },
        ]
        result = aggregate(records)
        assert result["last_invocation"] == "2026-03-21T12:00:00+00:00"
        assert result["system_prompt_tokens"] == 50
