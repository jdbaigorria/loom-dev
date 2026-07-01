"""
Bloque 3 — tests/unit/test_loaders.py

Cubre loom.core.loaders: prompt, tool, output, retry, session,
conversation, model y hook.
"""

import textwrap
import types
from pathlib import Path

import pytest

from loom.core.exceptions import AgentConfigError
from loom.schemas.config.conversations import (
    NullStrategy,
    SlidingWindowConfig,
    SlidingWindowsStrategy,
    SummarizingConfig,
    SummarizingStrategy,
)
from loom.schemas.config.prompt import PromptConfig
from loom.schemas.config.retry import RetryConfig
from loom.schemas.config.sessions import FileConfig, FileSession, S3Config, S3Session
from loom.schemas.config.tool import ToolConfig

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_loom_root(monkeypatch, tmp_path: Path) -> Path:
    """Apunta LOOM_ROOT a tmp_path y fija ``build_workspace_paths`` para loaders.prompt."""
    monkeypatch.setenv("LOOM_ROOT", str(tmp_path))
    from loom.core.paths import WorkspacePaths

    ws = WorkspacePaths(project_root=tmp_path, workspace_name="warp")
    monkeypatch.setattr("loom.core.loaders.prompt.build_workspace_paths", lambda **_: ws)
    return tmp_path


def write_tool_file(directory: Path, name: str, source: str) -> Path:
    """Escribe un archivo .py de tool en directory/tools/{name}.py"""
    tools_dir = directory / "tools"
    tools_dir.mkdir(parents=True, exist_ok=True)
    tool_file = tools_dir / f"{name}.py"
    tool_file.write_text(textwrap.dedent(source), encoding="utf-8")
    return tool_file


def write_tool_yaml(directory: Path, name: str, source: str, ext: str = "yaml") -> Path:
    """Escribe un archivo declarativo de tool en directory/tools/{name}.{ext}"""
    tools_dir = directory / "tools"
    tools_dir.mkdir(parents=True, exist_ok=True)
    tool_file = tools_dir / f"{name}.{ext}"
    tool_file.write_text(textwrap.dedent(source), encoding="utf-8")
    return tool_file


# ---------------------------------------------------------------------------
# loaders.prompt.get_prompt()
# ---------------------------------------------------------------------------


class TestGetPrompt:
    """LDR-01 a LDR-07"""

    def test_source_vacio_retorna_string_vacio(self, monkeypatch, tmp_path):
        """LDR-01: system_prompt vacío → AgentConfigError (empty prompt not allowed)"""
        make_loom_root(monkeypatch, tmp_path)
        from loom.core.loaders.prompt import get_prompt

        with pytest.raises(AgentConfigError):
            get_prompt(PromptConfig(prompt=""))

    def test_source_inline_retorna_texto_tal_cual(self, monkeypatch, tmp_path):
        """LDR-02: texto que no existe en disco → RawTextStrategy"""
        make_loom_root(monkeypatch, tmp_path)
        from loom.core.loaders.prompt import get_prompt

        result = get_prompt(PromptConfig(prompt="Eres un asistente experto"))
        assert result[0].get("text") == "Eres un asistente experto"

    def test_source_que_apunta_a_archivo_retorna_su_contenido(self, monkeypatch, tmp_path):
        """LDR-03: path relativo a un archivo .md → FileStrategy"""
        make_loom_root(monkeypatch, tmp_path)
        prompt_file = tmp_path / "prompt.md"
        prompt_file.write_text("# Mi Prompt\n\nContenido del prompt", encoding="utf-8")
        from loom.core.loaders.prompt import get_prompt

        result = get_prompt(PromptConfig(prompt="prompt.md"))
        text = result[0].get("text", "")
        assert "Mi Prompt" in text
        assert "Contenido del prompt" in text

    def test_source_que_apunta_a_directorio_concatena_archivos_ordenados(
        self, monkeypatch, tmp_path
    ):
        """LDR-04: path a directorio → DirectoryStrategy, archivos .md/.txt concatenados"""
        make_loom_root(monkeypatch, tmp_path)
        prompts_dir = tmp_path / "prompts"
        prompts_dir.mkdir()
        (prompts_dir / "01_ROL.md").write_text("ROL: experto", encoding="utf-8")
        (prompts_dir / "02_OBJETIVO.md").write_text("OBJETIVO: ayudar", encoding="utf-8")
        from loom.core.loaders.prompt import get_prompt

        result = get_prompt(PromptConfig(prompt="prompts"))
        text = result[0].get("text", "")
        assert "ROL: experto" in text
        assert "OBJETIVO: ayudar" in text
        # El orden debe ser ascendente (01 antes que 02)
        assert text.index("ROL") < text.index("OBJETIVO")

    def test_directorio_sin_archivos_validos_levanta_agent_config_error(
        self, monkeypatch, tmp_path
    ):
        """LDR-05: directorio vacío → AgentConfigError desde DirectoryStrategy"""
        make_loom_root(monkeypatch, tmp_path)
        empty_dir = tmp_path / "prompts"
        empty_dir.mkdir()
        from loom.core.loaders.prompt import get_prompt

        with pytest.raises(AgentConfigError, match="No valid files found"):
            get_prompt(PromptConfig(prompt="prompts"))

    def test_prefijo_s3_levanta_error_con_mensaje(self, monkeypatch, tmp_path):
        """LDR-06: s3:// → AgentConfigError con mensaje de no soportado"""
        make_loom_root(monkeypatch, tmp_path)
        from loom.core.loaders.prompt import get_prompt

        with pytest.raises(AgentConfigError, match="not yet supported"):
            get_prompt(PromptConfig(prompt="s3://mi-bucket/prompts/experto.md"))

    def test_prefijo_http_levanta_error_con_mensaje(self, monkeypatch, tmp_path):
        """LDR-07: http:// → AgentConfigError con mensaje de no soportado"""
        make_loom_root(monkeypatch, tmp_path)
        from loom.core.loaders.prompt import get_prompt

        with pytest.raises(AgentConfigError, match="not yet supported"):
            get_prompt(PromptConfig(prompt="https://ejemplo.com/prompt.md"))

    def test_base_path_resuelve_archivo_fuera_de_root(self, monkeypatch, tmp_path):
        """LDR-08: base_path apunta al config dir del agente → lee prompt.md correctamente

        Regresión: sin base_path, (project_root / 'prompt.md').resolve() apunta al
        root del proyecto donde el archivo no existe, y get_prompt retornaba el
        string 'prompt.md' en vez del contenido del archivo.
        """
        make_loom_root(monkeypatch, tmp_path)
        agent_config_dir = tmp_path / "warp" / "agents" / "my_agent" / "config"
        agent_config_dir.mkdir(parents=True)
        (agent_config_dir / "prompt.md").write_text("Eres un experto.", encoding="utf-8")

        from loom.core.loaders.prompt import get_prompt

        result = get_prompt(PromptConfig(prompt="prompt.md"), base_path=agent_config_dir)
        assert result[0].get("text") == "Eres un experto."

    def test_sin_base_path_archivo_fuera_de_root_lanza_error(self, monkeypatch, tmp_path):
        """LDR-09: sin base_path, archivo .md solo en config dir → AgentConfigError (not found)

        El archivo tiene extensión .md, por lo que _looks_like_file_path() retorna True
        y se lanza AgentConfigError en lugar de hacer fallback a texto inline.
        """
        make_loom_root(monkeypatch, tmp_path)
        agent_config_dir = tmp_path / "warp" / "agents" / "my_agent" / "config"
        agent_config_dir.mkdir(parents=True)
        (agent_config_dir / "prompt.md").write_text("Eres un experto.", encoding="utf-8")

        from loom.core.loaders.prompt import get_prompt

        # Sin base_path busca en project root → no encuentra el archivo → AgentConfigError
        with pytest.raises(AgentConfigError, match="not found"):
            get_prompt(PromptConfig(prompt="prompt.md"))

    def test_base_path_con_directorio_de_prompts(self, monkeypatch, tmp_path):
        """LDR-10: base_path + directorio de prompts → DirectoryStrategy desde config dir"""
        make_loom_root(monkeypatch, tmp_path)
        agent_config_dir = tmp_path / "warp" / "agents" / "my_agent" / "config"
        prompts_dir = agent_config_dir / "prompts"
        prompts_dir.mkdir(parents=True)
        (prompts_dir / "01_rol.md").write_text("ROL: experto", encoding="utf-8")
        (prompts_dir / "02_obj.md").write_text("OBJETIVO: ayudar", encoding="utf-8")

        from loom.core.loaders.prompt import get_prompt

        result = get_prompt(PromptConfig(prompt="prompts"), base_path=agent_config_dir)
        text = result[0].get("text", "")
        assert "ROL: experto" in text
        assert "OBJETIVO: ayudar" in text


class TestHydratePrompt:
    """hydrate_prompt() — resuelve file/dir a texto literal (ConfigSource hydration)."""

    def test_hidrata_archivo_a_texto_y_marca_resuelto(self, monkeypatch, tmp_path):
        """File ref → texto inline + is_resolved=True."""
        make_loom_root(monkeypatch, tmp_path)
        cfg_dir = tmp_path / "warp" / "agents" / "a" / "config"
        cfg_dir.mkdir(parents=True)
        (cfg_dir / "prompt.md").write_text("Eres un experto.", encoding="utf-8")

        from loom.core.loaders.prompt import hydrate_prompt

        result = hydrate_prompt(PromptConfig(prompt="prompt.md"), base_path=cfg_dir)

        assert result.is_resolved is True
        assert result.prompt == "Eres un experto."

    def test_idempotente_sobre_config_ya_resuelta(self):
        """Una config ya resuelta pasa sin cambios (misma instancia)."""
        from loom.core.loaders.prompt import hydrate_prompt

        already = PromptConfig(prompt="literal text", is_resolved=True)
        assert hydrate_prompt(already) is already

    def test_get_prompt_usa_texto_literal_sin_tocar_disco(self, monkeypatch, tmp_path):
        """is_resolved=True → get_prompt usa el texto verbatim aunque parezca un path."""
        make_loom_root(monkeypatch, tmp_path)
        from loom.core.loaders.prompt import get_prompt

        # Texto que contiene '/' (gatillaría la heurística de path si no fuese resuelto).
        cfg = PromptConfig(prompt="Usá rutas tipo a/b/c y respondé.", is_resolved=True)
        result = get_prompt(cfg)

        assert result[0].get("text") == "Usá rutas tipo a/b/c y respondé."


# ---------------------------------------------------------------------------
# utils.import_attr() + dotted-import code (tools/hooks/output via module:attr)
# ---------------------------------------------------------------------------


def _write_module(tmp_path, monkeypatch, modname: str, content: str) -> None:
    """Write an importable module to a tmp dir on sys.path."""
    (tmp_path / f"{modname}.py").write_text(textwrap.dedent(content), encoding="utf-8")
    monkeypatch.syspath_prepend(str(tmp_path))


class TestImportAttr:
    def test_colon_form(self, tmp_path, monkeypatch):
        from loom.utils.loaders import import_attr

        _write_module(tmp_path, monkeypatch, "ia_colon", "VALUE = 42\n")
        assert import_attr("ia_colon:VALUE") == 42

    def test_dot_form(self, tmp_path, monkeypatch):
        from loom.utils.loaders import import_attr

        _write_module(tmp_path, monkeypatch, "ia_dot", "VALUE = 7\n")
        assert import_attr("ia_dot.VALUE") == 7

    def test_sin_separador_levanta(self):
        from loom.utils.loaders import import_attr

        with pytest.raises(ValueError, match="module:attr"):
            import_attr("justaname")


class TestImportTool:
    """Tools referenciadas por dotted import (module:fn) — código instalado."""

    _FN_MODULE = """
        from strands import tool

        @tool
        def get_weather(city: str) -> str:
            \"\"\"Get weather for a city.\"\"\"
            return f"sunny in {city}"
    """

    _CLASS_MODULE = """
        from strands import tool

        class WeatherTools:
            def __init__(self, unit: str = "C"):
                self.unit = unit

            @tool
            def forecast(self, city: str) -> str:
                \"\"\"Forecast for a city.\"\"\"
                return f"{city}: 20{self.unit}"
    """

    def test_funcion_importada(self, tmp_path, monkeypatch):
        from loom.core.loaders.tool import get_tools

        _write_module(tmp_path, monkeypatch, "plug_fn", self._FN_MODULE)
        tool_def = ToolConfig.model_validate("plug_fn:get_weather")
        assert tool_def.source == "import"

        tools = get_tools([tool_def], tmp_path, tmp_path)
        assert len(tools) == 1
        assert tools[0].tool_spec["name"] == "get_weather"

    def test_clase_importada_con_params(self, tmp_path, monkeypatch):
        from loom.core.loaders.tool import get_tools

        _write_module(tmp_path, monkeypatch, "plug_cls", self._CLASS_MODULE)
        tool_def = ToolConfig.model_validate({"plug_cls:WeatherTools": {"unit": "F"}})

        tools = get_tools([tool_def], tmp_path, tmp_path)
        assert len(tools) == 1
        assert tools[0].tool_spec["name"] == "forecast"

    def test_ref_inexistente_levanta(self, tmp_path):
        from loom.core.exceptions import ToolLoadError
        from loom.core.loaders.tool import get_tools

        with pytest.raises(ToolLoadError, match="could not be imported"):
            get_tools([ToolConfig.model_validate("nope.module:thing")], tmp_path, tmp_path)

    def test_funcion_con_params_levanta(self, tmp_path, monkeypatch):
        from loom.core.exceptions import ToolLoadError
        from loom.core.loaders.tool import get_tools

        _write_module(tmp_path, monkeypatch, "plug_fn_p", self._FN_MODULE)
        tool_def = ToolConfig.model_validate({"plug_fn_p:get_weather": {"x": 1}})

        with pytest.raises(ToolLoadError, match="cannot take params"):
            get_tools([tool_def], tmp_path, tmp_path)


class TestImportHookAndOutput:
    """Hooks y output también aceptan la forma module:attr (código instalado)."""

    def test_hook_por_colon(self, tmp_path, monkeypatch):
        from loom.core.loaders.hook import get_hooks
        from loom.schemas.config.hook import HookConfig

        _write_module(
            tmp_path,
            monkeypatch,
            "plug_hook",
            """
            class MyHook:
                def __init__(self, level: str = "info"):
                    self.level = level

                def register_hooks(self, registry, **kwargs):
                    pass
            """,
        )
        hooks = get_hooks(
            [HookConfig.model_validate({"plug_hook:MyHook": {"level": "debug"}})], tmp_path
        )
        assert hooks[0].level == "debug"

    def test_output_por_colon(self, tmp_path, monkeypatch):
        from loom.core.loaders.output import get_output_class

        _write_module(
            tmp_path,
            monkeypatch,
            "plug_out",
            """
            from pydantic import BaseModel

            class MyOut(BaseModel):
                answer: str
            """,
        )
        cls = get_output_class("plug_out:MyOut", tmp_path)
        assert cls.__name__ == "MyOut"


class TestLoadersWithoutFilesystem:
    """Sin locator (paths=None): código local falla claro; plugin/registry funciona."""

    def test_tool_local_sin_locator_levanta(self):
        from loom.core.exceptions import ToolLoadError
        from loom.core.loaders.tool import get_tools

        with pytest.raises(ToolLoadError, match="no filesystem locator"):
            get_tools([ToolConfig.model_validate("local_tool")], None, None)

    def test_tool_import_sin_locator_ok(self, tmp_path, monkeypatch):
        from loom.core.loaders.tool import get_tools

        _write_module(tmp_path, monkeypatch, "nofs_plug", TestImportTool._FN_MODULE)
        tools = get_tools([ToolConfig.model_validate("nofs_plug:get_weather")], None, None)
        assert len(tools) == 1

    def test_output_local_sin_locator_levanta(self):
        from loom.core.exceptions import OutputLoadError
        from loom.core.loaders.output import get_output_class

        with pytest.raises(OutputLoadError, match="no filesystem locator"):
            get_output_class("LocalModel", None)

    def test_hook_local_sin_locator_levanta(self):
        from loom.core.exceptions import HookLoadError
        from loom.core.loaders.hook import get_hooks
        from loom.schemas.config.hook import HookConfig

        with pytest.raises(HookLoadError, match="no filesystem locator"):
            get_hooks([HookConfig.model_validate("local_hook")], None)

    def test_hook_registry_sin_locator_ok(self):
        from loom.core.loaders.hook import get_hooks
        from loom.schemas.config.hook import HookConfig

        hooks = get_hooks([HookConfig.model_validate("logging")], None)
        assert len(hooks) == 1


# ---------------------------------------------------------------------------
# loaders.tool._load_tool() / get_tools()
# ---------------------------------------------------------------------------


class TestToolLoader:
    """LDR-08 a LDR-16"""

    def test_archivo_de_tool_no_encontrado_levanta_error(self, tmp_path):
        """LDR-08: tool file inexistente → ToolLoadError"""
        from loom.core.exceptions import ToolLoadError
        from loom.core.loaders.tool import get_tools

        tool_def = ToolConfig.model_validate("missing_tool")
        with pytest.raises(ToolLoadError, match="missing_tool"):
            get_tools([tool_def], tmp_path, tmp_path)

    def test_tool_yaml_compila_builtin_con_nombre_del_archivo(self, tmp_path):
        """LDR-08b: un {name}.yaml especializa un builtin; el nombre es el del archivo."""
        from loom.core.loaders.tool import get_tools

        write_tool_yaml(
            tmp_path,
            "get_pokemon",
            """
            builtin: apicall
            description: Fetch a Pokémon by name or id.
            bind:
              base_url: https://pokeapi.co/api/v2
              path: /pokemon/{name_or_id}
              method: GET
            expose:
              name_or_id:
                type: string
                required: true
                description: Name or id.
            """,
        )
        tool_def = ToolConfig.model_validate("get_pokemon")
        result = get_tools([tool_def], tmp_path, tmp_path)
        assert len(result) == 1
        assert result[0].tool_name == "get_pokemon"
        assert set(result[0].tool_spec["inputSchema"]["json"]["properties"]) == {"name_or_id"}

    def test_tool_yaml_sin_builtin_levanta_error(self, tmp_path):
        """LDR-08c: un tool YAML sin 'builtin' → ToolLoadError."""
        from loom.core.exceptions import ToolLoadError
        from loom.core.loaders.tool import get_tools

        write_tool_yaml(tmp_path, "bad", "description: x\n")
        with pytest.raises(ToolLoadError, match="must declare 'builtin"):
            get_tools([ToolConfig.model_validate("bad")], tmp_path, tmp_path)

    def test_tool_yaml_con_name_levanta_error(self, tmp_path):
        """LDR-08d: el archivo no debe fijar 'name' (lo da el nombre del archivo)."""
        from loom.core.exceptions import ToolLoadError
        from loom.core.loaders.tool import get_tools

        write_tool_yaml(tmp_path, "x", "builtin: apicall\nname: other\n")
        with pytest.raises(ToolLoadError, match="must not set 'name'"):
            get_tools([ToolConfig.model_validate("x")], tmp_path, tmp_path)

    def test_tool_definida_como_py_y_yaml_es_ambigua(self, tmp_path):
        """LDR-08e: el mismo nombre como .py y .yaml → error de ambigüedad."""
        from loom.core.exceptions import ToolLoadError
        from loom.core.loaders.tool import get_tools

        write_tool_file(tmp_path, "dup", "def t(): pass\nt.tool_spec = {'name': 't'}\n")
        write_tool_yaml(tmp_path, "dup", "builtin: apicall\n")
        with pytest.raises(ToolLoadError, match="both .py and"):
            get_tools([ToolConfig.model_validate("dup")], tmp_path, tmp_path)

    def test_tool_yaml_no_acepta_params_inline(self, tmp_path):
        """LDR-08f: una tool YAML se referencia sin params; pasarlos → error."""
        from loom.core.exceptions import ToolLoadError
        from loom.core.loaders.tool import get_tools

        write_tool_yaml(tmp_path, "p", "builtin: apicall\n")
        tool_def = ToolConfig.model_validate({"p": {"x": 1}})
        with pytest.raises(ToolLoadError, match="cannot take inline params"):
            get_tools([tool_def], tmp_path, tmp_path)

    def test_modulo_sin_tools_decoradas_levanta_error(self, tmp_path):
        """LDR-09: módulo sin tool_spec → ToolLoadError"""
        from loom.core.exceptions import ToolLoadError
        from loom.core.loaders.tool import get_tools

        write_tool_file(
            tmp_path,
            "empty_tool",
            """
            def some_function():
                pass
        """,
        )
        tool_def = ToolConfig.model_validate("empty_tool")
        with pytest.raises(ToolLoadError, match="No valid tools found"):
            get_tools([tool_def], tmp_path, tmp_path)

    def test_funciones_con_tool_spec_son_extraidas(self, tmp_path):
        """LDR-10: funciones con atributo tool_spec → lista de callables"""
        from loom.core.loaders.tool import get_tools

        write_tool_file(
            tmp_path,
            "func_tool",
            """
            def tool_a():
                pass
            tool_a.tool_spec = {"name": "tool_a"}

            def tool_b():
                pass
            tool_b.tool_spec = {"name": "tool_b"}
        """,
        )
        tool_def = ToolConfig.model_validate("func_tool")
        result = get_tools([tool_def], tmp_path, tmp_path)

        assert len(result) == 2
        assert all(callable(t) for t in result)

    def test_clase_con_metodos_tool_spec_instancia_y_extrae_metodos(self, tmp_path):
        """LDR-11: clase con métodos decorados → instancia la clase y extrae métodos"""
        from loom.core.loaders.tool import get_tools

        write_tool_file(
            tmp_path,
            "classtool",
            """
            class Classtool:
                def method_a(self):
                    pass
                def method_b(self):
                    pass

            Classtool.method_a.tool_spec = {"name": "method_a"}
            Classtool.method_b.tool_spec = {"name": "method_b"}
        """,
        )
        tool_def = ToolConfig.model_validate("classtool")
        result = get_tools([tool_def], tmp_path, tmp_path)

        assert len(result) == 2

    def test_clase_con_params_se_instancia_con_los_params_del_yaml(self, tmp_path):
        """LDR-12: clase + params en YAML → se instancia con kwargs"""
        from loom.core.loaders.tool import get_tools

        write_tool_file(
            tmp_path,
            "paramtool",
            """
            class Paramtool:
                def __init__(self, api_key: str):
                    self.api_key = api_key

                def call(self):
                    pass
            Paramtool.call.tool_spec = {"name": "call"}
        """,
        )
        tool_def = ToolConfig.model_validate({"paramtool": {"api_key": "abc-123"}})
        result = get_tools([tool_def], tmp_path, tmp_path)

        assert len(result) == 1
        # El método bound tiene acceso al api_key del objeto instanciado
        assert result[0].__self__.api_key == "abc-123"

    def test_params_sin_clase_en_modulo_levanta_error(self, tmp_path):
        """LDR-13: params definidos pero sin clase en módulo → ToolLoadError"""
        from loom.core.exceptions import ToolLoadError
        from loom.core.loaders.tool import get_tools

        write_tool_file(
            tmp_path,
            "noclasswithparams",
            """
            def my_func():
                pass
            my_func.tool_spec = True
        """,
        )
        tool_def = ToolConfig.model_validate({"noclasswithparams": {"key": "val"}})
        with pytest.raises(ToolLoadError, match="declares params"):
            get_tools([tool_def], tmp_path, tmp_path)

    def test_tool_shared_busca_en_shared_dir(self, tmp_path):
        """LDR-14: is_shared=True → busca en shared_dir/tools/"""
        from loom.core.loaders.tool import get_tools

        agent_dir = tmp_path / "agent"
        shared_dir = tmp_path / "shared"

        # Tool sólo existe en shared_dir
        write_tool_file(
            shared_dir,
            "shared_func",
            """
            def shared_func():
                pass
            shared_func.tool_spec = True
        """,
        )
        tool_def = ToolConfig.model_validate("shared.shared_func")
        result = get_tools([tool_def], agent_dir, shared_dir / "tools")

        assert len(result) == 1

    def test_tool_no_shared_busca_en_agent_dir(self, tmp_path):
        """LDR-15: is_shared=False → busca en agent_dir/tools/"""
        from loom.core.loaders.tool import get_tools

        agent_dir = tmp_path / "agent"
        shared_dir = tmp_path / "shared" / "tools"

        # Tool sólo existe en agent_dir
        write_tool_file(
            agent_dir,
            "local_tool",
            """
            def local_tool():
                pass
            local_tool.tool_spec = True
        """,
        )

        tool_def = ToolConfig.model_validate("local_tool")
        result = get_tools([tool_def], agent_dir, shared_dir)

        assert len(result) == 1

    def test_get_tools_retorna_lista_plana_no_lista_de_listas(self, tmp_path):
        """LDR-16: múltiples tools con múltiples callables → lista plana"""
        from loom.core.loaders.tool import get_tools

        write_tool_file(
            tmp_path,
            "tool_uno",
            """
            def fn_a():
                pass
            fn_a.tool_spec = True
            def fn_b():
                pass
            fn_b.tool_spec = True
        """,
        )
        write_tool_file(
            tmp_path,
            "tool_dos",
            """
            def fn_c():
                pass
            fn_c.tool_spec = True
        """,
        )
        defs = [
            ToolConfig.model_validate("tool_uno"),
            ToolConfig.model_validate("tool_dos"),
        ]
        result = get_tools(defs, tmp_path, tmp_path)

        assert len(result) == 3
        # Ningún elemento es una lista (lista plana)
        assert not any(isinstance(t, list) for t in result)


# ---------------------------------------------------------------------------
# loaders.output.get_output_class()
# ---------------------------------------------------------------------------


class TestOutputLoader:
    """LDR-17 a LDR-20"""

    def test_dotted_path_importa_clase_de_modulo(self, tmp_path, monkeypatch):
        """LDR-17: 'module.ClassName' → importa por dotted path"""
        # Usamos una clase de pydantic ya disponible como proxy
        from pydantic import BaseModel

        from loom.core.loaders.output import get_output_class

        result = get_output_class("pydantic.BaseModel", tmp_path)
        assert result is BaseModel

    def test_nombre_simple_carga_desde_output_py_del_agente(self, tmp_path):
        """LDR-18: sin punto → carga clase de agent_dir/output.py"""
        from loom.core.loaders.output import get_output_class

        output_file = tmp_path / "output.py"
        output_file.write_text(
            textwrap.dedent("""
            from pydantic import BaseModel

            class MyOutput(BaseModel):
                result: str
                reasoning: str
        """),
            encoding="utf-8",
        )

        result = get_output_class("MyOutput", tmp_path)

        assert result.__name__ == "MyOutput"

    def test_output_py_no_encontrado_levanta_file_not_found(self, tmp_path):
        """LDR-19: output.py inexistente → OutputLoadError"""
        from loom.core.exceptions import OutputLoadError
        from loom.core.loaders.output import get_output_class

        with pytest.raises(OutputLoadError, match="Output file not found"):
            get_output_class("MissingClass", tmp_path)

    def test_clase_no_encontrada_en_output_py_levanta_attribute_error(self, tmp_path):
        """LDR-20: clase no existe en output.py → OutputLoadError"""
        from loom.core.exceptions import OutputLoadError
        from loom.core.loaders.output import get_output_class

        output_file = tmp_path / "output.py"
        output_file.write_text(
            textwrap.dedent("""
            from pydantic import BaseModel
            class RealClass(BaseModel):
                value: str
        """),
            encoding="utf-8",
        )

        with pytest.raises(OutputLoadError, match="not found"):
            get_output_class("WrongClassName", tmp_path)


# ---------------------------------------------------------------------------
# loaders.retry.get_retry_strategy()
# ---------------------------------------------------------------------------


class TestRetryLoader:
    """LDR-21 a LDR-22"""

    def test_perfil_low_resuelve_del_profile(self):
        """LDR-21: perfil 'low' → ModelRetryStrategy con los valores del built-in profile"""
        from loom.config.profiles import get_profiles
        from loom.core.loaders.retry import get_retry_strategy

        result = get_retry_strategy("low")
        low = get_profiles().retry["low"]
        assert result._max_attempts == low.max_attempts
        assert result._initial_delay == low.initial_delay

    def test_config_inline_usa_la_config_personalizada(self):
        """LDR-22: retry inline → ModelRetryStrategy con esos valores"""
        from loom.core.loaders.retry import get_retry_strategy

        result = get_retry_strategy(RetryConfig(max_attempts=10, initial_delay=2.0, max_delay=60.0))
        assert result._max_attempts == 10
        assert result._initial_delay == 2.0

    def test_profile_desconocido_levanta_error(self):
        """Bonus: profile inexistente → AgentConfigError"""
        from loom.core.exceptions import AgentConfigError
        from loom.core.loaders.retry import get_retry_strategy

        with pytest.raises(AgentConfigError, match="Unknown retry profile"):
            get_retry_strategy("turbo")

    @pytest.mark.parametrize("profile", ["low", "medium", "high"])
    def test_todos_los_perfiles_predefinidos_retornan_estrategia(self, profile):
        """Bonus: todos los perfiles built-in generan un ModelRetryStrategy"""
        from loom.adapters.strands import ModelRetryStrategy
        from loom.core.loaders.retry import get_retry_strategy

        assert isinstance(get_retry_strategy(profile), ModelRetryStrategy)


# ---------------------------------------------------------------------------
# loaders.session.get_session_manager()
# ---------------------------------------------------------------------------


class TestSessionLoader:
    """LDR-23 a LDR-24"""

    def test_proveedor_desconocido_levanta_agent_config_error(self):
        """LDR-23: provider no registrado → AgentConfigError"""
        from loom.core.loaders.session import get_session_manager

        # Creamos un SessionConfig falso con provider inválido
        fake_config = types.SimpleNamespace(
            provider="redis",
            config=types.SimpleNamespace(model_dump=lambda: {"path": "/tmp"}),
        )
        with pytest.raises(AgentConfigError, match="Invalid session manager type"):
            get_session_manager(fake_config, "session-123")

    def test_proveedor_file_crea_file_session_manager(self, mocker):
        """LDR-24: provider='file' → FileSessionManager con session_id y `path`
        mapeado a `storage_dir` (lo que el constructor de Strands espera; sin el
        remap la ruta cae en **kwargs y Strands usa /tmp/strands/sessions)."""
        from loom.core.loaders.session import get_session_manager

        # Patch the registry dict since it holds direct references bound at import time
        mock_cls = mocker.Mock()
        mocker.patch.dict("loom.core.loaders.session.SESSION_MANAGER_REGISTRY", {"file": mock_cls})
        session_config = FileSession(provider="file", config=FileConfig(path=".loom/sessions"))

        get_session_manager(session_config, "test-session-id")

        mock_cls.assert_called_once_with(
            session_id="test-session-id", storage_dir=".loom/sessions"
        )

    def test_proveedor_s3_crea_s3_session_manager(self, mocker):
        """Bonus: provider='s3' → instancia S3SessionManager"""
        from loom.core.loaders.session import get_session_manager

        # Patch the registry dict to avoid real S3 API calls
        mock_cls = mocker.Mock()
        mocker.patch.dict("loom.core.loaders.session.SESSION_MANAGER_REGISTRY", {"s3": mock_cls})
        session_config = S3Session(
            provider="s3", config=S3Config(bucket="my-bucket", prefix="sessions/")
        )

        get_session_manager(session_config, "sess-456")

        mock_cls.assert_called_once_with(
            session_id="sess-456", bucket="my-bucket", prefix="sessions/"
        )


# ---------------------------------------------------------------------------
# loaders.conversation.get_conversation_manager()
# ---------------------------------------------------------------------------


class TestConversationLoader:
    """LDR-25 a LDR-27"""

    def test_estrategia_desconocida_levanta_agent_config_error(self):
        """LDR-25: strategy no registrada → AgentConfigError"""
        from loom.core.loaders.conversation import get_conversation_manager

        fake_config = types.SimpleNamespace(strategy="unknown", config=None)
        with pytest.raises(AgentConfigError, match="Invalid conversation manager type"):
            get_conversation_manager(fake_config)

    def test_estrategia_null_retorna_null_conversation_manager(self):
        """LDR-26: strategy='null' → NullConversationManager"""
        from loom.adapters.strands import NullConversationManager
        from loom.core.loaders.conversation import get_conversation_manager

        config = NullStrategy(strategy="null")
        result = get_conversation_manager(config)

        assert isinstance(result, NullConversationManager)

    def test_estrategia_sliding_window_retorna_sliding_window_manager(self):
        """LDR-27: strategy='sliding_window' → SlidingWindowConversationManager"""
        from loom.adapters.strands import SlidingWindowConversationManager
        from loom.core.loaders.conversation import get_conversation_manager

        config = SlidingWindowsStrategy(
            strategy="sliding_window",
            config=SlidingWindowConfig(window_size=5),
        )
        result = get_conversation_manager(config)

        assert isinstance(result, SlidingWindowConversationManager)

    def test_estrategia_summarizing_llama_al_builder(self, mocker):
        """Bonus: strategy='summarizing' → invoca _build_summarizing_manager"""
        from loom.core.loaders.conversation import get_conversation_manager

        # Patch the registry dict since it holds direct function references bound at import time
        mock_builder = mocker.Mock(return_value=mocker.Mock())
        mocker.patch.dict(
            "loom.core.loaders.conversation.CONVERSATION_MANAGER_REGISTRY",
            {"summarizing": mock_builder},
        )
        config = SummarizingStrategy(
            strategy="summarizing",
            config=SummarizingConfig(),
        )
        get_conversation_manager(config)

        mock_builder.assert_called_once()


# ---------------------------------------------------------------------------
# loaders.model.get_model()
# ---------------------------------------------------------------------------


class TestModelLoader:
    """LDR-28 a LDR-30"""

    def test_profile_desconocido_levanta_model_load_error(self):
        """LDR-28: profile name inexistente → ModelLoadError"""
        from loom.core.exceptions import ModelLoadError
        from loom.core.loaders.model import resolve_model_config

        with pytest.raises(ModelLoadError, match="Unknown model profile"):
            resolve_model_config("does_not_exist")

    def test_profile_name_resuelve_a_su_config(self):
        """LDR-29: profile name → CustomModelConfig del profile (built-in 'default')"""
        from loom.core.loaders.model import resolve_model_config

        cfg = resolve_model_config("default")
        assert "BedrockModel" in cfg.import_path
        assert cfg.model_id  # default profile carries a model_id

    def test_custom_import_path_invalido_levanta_model_load_error(self):
        """LDR-30: provider='custom' con import_path irresoluble → ModelLoadError"""
        from loom.core.exceptions import ModelLoadError
        from loom.core.loaders.model import _build_custom_model
        from loom.schemas.config.models import CustomModelConfig

        config = CustomModelConfig(import_path="strands.models.nope.DoesNotExist")
        with pytest.raises(ModelLoadError, match="Could not import model class"):
            _build_custom_model(config)

    def test_custom_passthrough_instancia_la_clase_con_params(self, mocker):
        """LDR-31: provider='custom' resuelve import_path y construye con params"""
        from loom.core.loaders.model import _build_custom_model
        from loom.schemas.config.models import CustomModelConfig

        fake_cls = mocker.Mock(return_value="model-instance")
        mocker.patch("loom.adapters.strands.resolve", return_value=fake_cls)

        config = CustomModelConfig(
            import_path="my.pkg.MyModel", params={"model_id": "x", "temperature": 0.3}
        )
        result = _build_custom_model(config)

        fake_cls.assert_called_once_with(model_id="x", temperature=0.3)
        assert result == "model-instance"

    def test_provider_alias_resuelve_import_path_y_construye(self, mocker):
        """LDR-32: provider='openai' resuelve al import_path built-in y construye con params"""
        from loom.core.loaders.model import _build_custom_model
        from loom.schemas.config.models import CustomModelConfig

        fake_cls = mocker.Mock(return_value="model-instance")
        resolve = mocker.patch("loom.adapters.strands.resolve", return_value=fake_cls)

        config = CustomModelConfig(provider="openai", params={"model_id": "gpt-4o"})
        result = _build_custom_model(config)

        resolve.assert_called_once_with("strands.models.openai.OpenAIModel", optional=True)
        fake_cls.assert_called_once_with(model_id="gpt-4o")
        assert result == "model-instance"

    def test_provider_desconocido_levanta_model_load_error(self):
        """LDR-33: provider sin alias → ModelLoadError (Unknown model provider)"""
        from loom.core.exceptions import ModelLoadError
        from loom.core.loaders.model import resolve_import_path
        from loom.schemas.config.models import CustomModelConfig

        config = CustomModelConfig(provider="no_such_provider", params={"model_id": "m"})
        with pytest.raises(ModelLoadError, match="Unknown model provider"):
            resolve_import_path(config)


# ---------------------------------------------------------------------------
# loaders.hook.get_hooks() (GAP-01A)
# ---------------------------------------------------------------------------


class TestHookLoader:
    """LDR-H01 a LDR-H07"""

    def test_builtin_logging_carga_sin_params(self, tmp_path):
        """LDR-H01: 'logging' en REGISTRY → instancia LoggingHook sin params"""
        from loom.core.loaders.hook import get_hooks
        from loom.hooks.logging_hook import LoggingHook
        from loom.schemas.config.hook import HookConfig

        hooks = get_hooks([HookConfig.model_validate("logging")], tmp_path)

        assert len(hooks) == 1
        assert isinstance(hooks[0], LoggingHook)

    def test_builtin_rate_limit_con_params(self, tmp_path):
        """LDR-H02: 'rate_limit' con max_calls=5 → RateLimitHook(max_calls=5)"""
        from loom.core.loaders.hook import get_hooks
        from loom.hooks.rate_limit import RateLimitHook
        from loom.schemas.config.hook import HookConfig

        cfg = HookConfig.model_validate({"rate_limit": {"max_calls": 5}})
        hooks = get_hooks([cfg], tmp_path)

        assert isinstance(hooks[0], RateLimitHook)
        assert hooks[0]._max_calls == 5

    def test_builtin_tool_tracker_carga(self, tmp_path):
        """LDR-H03: 'tool_tracker' en REGISTRY → instancia ToolTrackerHook"""
        from loom.core.loaders.hook import get_hooks
        from loom.hooks.tool_tracker import ToolTrackerHook
        from loom.schemas.config.hook import HookConfig

        hooks = get_hooks([HookConfig.model_validate("tool_tracker")], tmp_path)

        assert isinstance(hooks[0], ToolTrackerHook)

    def test_local_hook_descubierto_por_convencion(self, tmp_path):
        """LDR-H04: hook local en hooks_dir descubierto por nombre PascalCase"""

        from loom.core.loaders.hook import get_hooks
        from loom.schemas.config.hook import HookConfig

        hook_file = tmp_path / "my_hook.py"
        hook_file.write_text(
            "from strands.hooks import HookProvider, HookRegistry\n"
            "class MyHook(HookProvider):\n"
            "    def register_hooks(self, registry: HookRegistry, **kwargs): pass\n",
            encoding="utf-8",
        )

        hooks = get_hooks([HookConfig.model_validate("my_hook")], tmp_path)

        assert len(hooks) == 1
        assert type(hooks[0]).__name__ == "MyHook"

    def test_hook_local_no_existe_lanza_error(self, tmp_path):
        """LDR-H05: hook local no encontrado → HookLoadError"""
        from loom.core.exceptions import HookLoadError
        from loom.core.loaders.hook import get_hooks
        from loom.schemas.config.hook import HookConfig

        with pytest.raises(HookLoadError, match="ghost_hook"):
            get_hooks([HookConfig.model_validate("ghost_hook")], tmp_path)

    def test_hook_qualified_importable(self, tmp_path):
        """LDR-H06: fully qualified 'loom.hooks.logging_hook.LoggingHook' → carga OK"""
        from loom.core.loaders.hook import get_hooks
        from loom.hooks.logging_hook import LoggingHook
        from loom.schemas.config.hook import HookConfig

        cfg = HookConfig.model_validate("loom.hooks.logging_hook.LoggingHook")
        hooks = get_hooks([cfg], tmp_path)

        assert isinstance(hooks[0], LoggingHook)

    def test_hook_qualified_no_importable_lanza_error(self, tmp_path):
        """LDR-H07: fully qualified módulo inexistente → HookLoadError"""
        from loom.core.exceptions import HookLoadError
        from loom.core.loaders.hook import get_hooks
        from loom.schemas.config.hook import HookConfig

        cfg = HookConfig.model_validate("no.existe.EsteHook")
        with pytest.raises(HookLoadError):
            get_hooks([cfg], tmp_path)


# ---------------------------------------------------------------------------
# loaders.session — custom provider passthrough (DynamoDB/Redis/… via import_path)
# ---------------------------------------------------------------------------


class TestCustomSessionSeam:
    def test_custom_resuelve_e_instancia_con_session_id_y_params(self, monkeypatch):
        """LDR-SC01: provider=custom importa la clase y la construye con session_id + config."""
        from loom.core.loaders.session import get_session_manager
        from loom.schemas.config.sessions import CustomSession

        captured: dict = {}

        class DummySM:
            def __init__(self, session_id, **kwargs):
                captured["session_id"] = session_id
                captured["kwargs"] = kwargs

        monkeypatch.setattr("loom.adapters.strands.resolve", lambda *p, **k: DummySM)

        cfg = CustomSession(
            import_path="my.pkg:DummySM",
            config={"table": "sessions", "region": "us-east-1"},
        )
        mgr = get_session_manager(cfg, session_id="s-1")

        assert isinstance(mgr, DummySM)
        assert captured["session_id"] == "s-1"
        assert captured["kwargs"] == {"table": "sessions", "region": "us-east-1"}

    def test_custom_import_path_irresoluble_lanza(self):
        """LDR-SC02: import_path inexistente → AgentConfigError con el path en el mensaje."""
        from loom.core.loaders.session import get_session_manager
        from loom.schemas.config.sessions import CustomSession

        cfg = CustomSession(import_path="no.existe:Nope")
        with pytest.raises(AgentConfigError, match="no.existe:Nope"):
            get_session_manager(cfg, session_id="s-1")

    def test_custom_discrimina_por_provider(self):
        """LDR-SC03: un dict con provider=custom valida como CustomSession."""
        from pydantic import TypeAdapter

        from loom.schemas.config.sessions import CustomSession, SessionConfig

        parsed = TypeAdapter(SessionConfig).validate_python(
            {"provider": "custom", "import_path": "my.pkg:DynamoSession", "config": {"table": "t"}}
        )
        assert isinstance(parsed, CustomSession)
        assert parsed.import_path == "my.pkg:DynamoSession"


# ---------------------------------------------------------------------------
# loaders.conversation — custom strategy passthrough (via import_path)
# ---------------------------------------------------------------------------


class TestCustomConversationSeam:
    def test_custom_resuelve_e_instancia_con_params(self, monkeypatch):
        """LDR-CC01: strategy=custom importa la clase y la construye con config."""
        from loom.core.loaders.conversation import get_conversation_manager
        from loom.schemas.config.conversations import CustomStrategy

        captured: dict = {}

        class DummyCM:
            def __init__(self, **kwargs):
                captured["kwargs"] = kwargs

        monkeypatch.setattr("loom.adapters.strands.resolve", lambda *p, **k: DummyCM)

        cfg = CustomStrategy(strategy="custom", import_path="my.pkg:DummyCM", config={"window": 5})
        mgr = get_conversation_manager(cfg)

        assert isinstance(mgr, DummyCM)
        assert captured["kwargs"] == {"window": 5}

    def test_custom_import_path_irresoluble_lanza(self):
        """LDR-CC02: import_path inexistente → AgentConfigError con el path en el mensaje."""
        from loom.core.loaders.conversation import get_conversation_manager
        from loom.schemas.config.conversations import CustomStrategy

        cfg = CustomStrategy(strategy="custom", import_path="no.existe:Nope")
        with pytest.raises(AgentConfigError, match="no.existe:Nope"):
            get_conversation_manager(cfg)

    def test_custom_discrimina_por_strategy(self):
        """LDR-CC03: un dict con strategy=custom valida como CustomStrategy."""
        from pydantic import TypeAdapter

        from loom.schemas.config.conversations import ConversationConfig, CustomStrategy

        parsed = TypeAdapter(ConversationConfig).validate_python(
            {"strategy": "custom", "import_path": "my.pkg:MyCM", "config": {"k": 1}}
        )
        assert isinstance(parsed, CustomStrategy)
        assert parsed.import_path == "my.pkg:MyCM"
