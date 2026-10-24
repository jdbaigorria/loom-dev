"""
Bloque 1 — tests/unit/test_schemas.py

Cubre los validators custom y comportamientos críticos de los schemas Pydantic.
"""

import pytest
from pydantic import ValidationError

from loom.schemas.config.conversations import SummarizationAgentConfig, SummarizingConfig
from loom.schemas.config.loom import LoomConfig
from loom.schemas.config.models import CustomModelConfig
from loom.schemas.config.prompt import PromptConfig
from loom.schemas.config.retry import RetryConfig
from loom.schemas.config.tool import ToolConfig
from loom.schemas.context import LoomSession
from loom.schemas.request import (
    AgentComplexRequest,
    AgentRequest,
    ByteSource,
    LocationS3,
    SourceFileS3,
)
from loom.schemas.response import AgentResponse, AgentResponseMetadata

# ---------------------------------------------------------------------------
# ToolConfig — validator parse_mixed_list
# ---------------------------------------------------------------------------


class TestToolConfig:
    """SCH-T01 a SCH-T05"""

    def test_string_simple_crea_tool_no_compartida(self):
        """SCH-T01: string sin prefijo → is_shared=False, params={}"""
        tool = ToolConfig.model_validate("my_tool")
        assert tool.name == "my_tool"
        assert tool.is_shared is False
        assert tool.params == {}

    def test_string_con_prefijo_shared_detecta_herramienta_compartida(self):
        """SCH-T02: 'shared.X' → is_shared=True, name sin prefijo"""
        tool = ToolConfig.model_validate("shared.my_tool")
        assert tool.name == "my_tool"
        assert tool.is_shared is True

    def test_dict_simple_extrae_name_y_params(self):
        """SCH-T03: dict con nombre simple → name y params correctos"""
        tool = ToolConfig.model_validate({"my_tool": {"key": "val"}})
        assert tool.name == "my_tool"
        assert tool.params == {"key": "val"}
        assert tool.is_shared is False

    def test_dict_con_prefijo_shared_detecta_herramienta_compartida(self):
        """SCH-T04: dict con 'shared.' → is_shared=True"""
        tool = ToolConfig.model_validate({"shared.my_tool": {"k": 1}})
        assert tool.name == "my_tool"
        assert tool.is_shared is True
        assert tool.params == {"k": 1}

    def test_dict_con_valor_none_produce_params_vacio(self):
        """SCH-T05: dict con value None → params={}"""
        tool = ToolConfig.model_validate({"my_tool": None})
        assert tool.params == {}

    def test_string_con_prefijo_builtin_detecta_source_builtin(self):
        """SCH-T06: 'builtin.X' → source='builtin', is_builtin=True, name sin prefijo"""
        tool = ToolConfig.model_validate("builtin.kb")
        assert tool.name == "kb"
        assert tool.source == "builtin"
        assert tool.is_builtin is True
        assert tool.is_shared is False

    def test_dict_con_prefijo_builtin_conserva_params(self):
        """SCH-T07: dict 'builtin.apicall' con params → source builtin + params intactos"""
        tool = ToolConfig.model_validate(
            {"builtin.apicall": {"name": "weather_api", "allowed_paths": ["/v1/*"]}}
        )
        assert tool.name == "apicall"
        assert tool.is_builtin is True
        assert tool.params == {"name": "weather_api", "allowed_paths": ["/v1/*"]}

    def test_source_por_defecto_es_file(self):
        """SCH-T08: tool sin prefijo → source='file'"""
        tool = ToolConfig.model_validate("plain_tool")
        assert tool.source == "file"
        assert tool.is_builtin is False
        assert tool.is_shared is False

    def test_referencia_con_dos_puntos_es_import(self):
        """SCH-T09: 'module:fn' → source='import', nombre = referencia completa"""
        tool = ToolConfig.model_validate("my.pkg.tools:get_weather")
        assert tool.source == "import"
        assert tool.name == "my.pkg.tools:get_weather"

    def test_yaml_form_builtin_separa_registry_key_del_nombre(self):
        """SCH-T10: dict estructurado (hidratado) conserva builtin/registry_key"""
        tool = ToolConfig.model_validate(
            {"name": "get_pokemon", "source": "builtin", "builtin": "apicall", "params": {}}
        )
        assert tool.name == "get_pokemon"
        assert tool.builtin == "apicall"
        assert tool.registry_key == "apicall"


# ---------------------------------------------------------------------------
# PromptConfig — validator wrap_str_in_dict
# ---------------------------------------------------------------------------


class TestPromptConfig:
    """SCH-P01 a SCH-P02"""

    def test_string_queda_envuelto_como_system_prompt(self):
        """SCH-P01: string → {prompt: string}"""
        config = PromptConfig.model_validate("prompt.md")
        assert config.prompt == "prompt.md"

    def test_dict_pasado_directamente_no_se_modifica(self):
        """SCH-P02: dict válido pasa sin transformación"""
        config = PromptConfig.model_validate({"system_prompt": "Eres un asistente"})
        assert config.prompt == "Eres un asistente"


# ---------------------------------------------------------------------------
# RetryConfig
# ---------------------------------------------------------------------------


class TestRetryConfig:
    """SCH-R04, SCH-R05"""

    def test_initial_delay_mayor_que_max_delay_levanta_error(self):
        """SCH-R04: initial_delay > max_delay → ValidationError"""
        with pytest.raises(ValidationError):
            RetryConfig(initial_delay=5.0, max_delay=1.0)

    def test_initial_delay_igual_a_max_delay_es_valido(self):
        """SCH-R05: initial_delay == max_delay → ok"""
        config = RetryConfig(initial_delay=1.0, max_delay=1.0)
        assert config.initial_delay == config.max_delay


class TestRetryConfigInline:
    """Inline retry config (profile resolution is covered in test_profiles.py)."""

    def test_inline_config_valido(self):
        config = RetryConfig(max_attempts=10, initial_delay=1.0, max_delay=30.0)
        assert config.max_attempts == 10

    def test_initial_mayor_que_max_levanta_error(self):
        with pytest.raises(ValidationError):
            RetryConfig(initial_delay=10.0, max_delay=1.0)


# ---------------------------------------------------------------------------
# LoomSession — UUIDs únicos por instancia
# ---------------------------------------------------------------------------


class TestLoomSession:
    """SCH-S01 a SCH-S03"""

    def test_campos_requeridos_se_asignan(self):
        """SCH-S01: user_id y session_id requeridos → se asignan correctamente"""
        s = LoomSession(user_id="u-123", session_id="s-abc")
        assert s.user_id == "u-123"
        assert s.session_id == "s-abc"

    def test_is_anonymous_por_defecto_es_false(self):
        """SCH-S02: is_anonymous por defecto es False"""
        s = LoomSession(user_id="u-1", session_id="s-1")
        assert s.is_anonymous is False

    def test_is_anonymous_puede_setearse_a_true(self):
        """SCH-S03: is_anonymous se puede marcar explícitamente"""
        s = LoomSession(user_id="anon-xyz", session_id="s-1", is_anonymous=True)
        assert s.is_anonymous is True

    def test_sin_campos_requeridos_lanza_error(self):
        """Bonus: omitir user_id o session_id → ValidationError"""
        with pytest.raises(ValidationError):
            LoomSession(user_id="u-1")


# ---------------------------------------------------------------------------
# CustomModelConfig (inline passthrough)
# ---------------------------------------------------------------------------


class TestCustomModelConfig:
    def test_build_model_returns_params(self):
        config = CustomModelConfig(
            import_path="strands.models.bedrock.BedrockModel",
            params={"model_id": "x", "temperature": 0.5},
        )
        assert config.build_model() == {"model_id": "x", "temperature": 0.5}

    def test_model_id_property_reads_from_params(self):
        assert CustomModelConfig(import_path="a.B", params={"model_id": "m"}).model_id == "m"
        assert CustomModelConfig(import_path="a.B").model_id is None

    def test_extra_fields_forbidden(self):
        with pytest.raises(ValidationError):
            CustomModelConfig(import_path="a.B", bogus=1)

    def test_provider_alias_accepted(self):
        config = CustomModelConfig(provider="openai", params={"model_id": "gpt-4o"})
        assert config.provider == "openai"
        assert config.import_path is None
        assert config.model_id == "gpt-4o"

    def test_neither_provider_nor_import_path_rejected(self):
        with pytest.raises(ValidationError, match="either 'provider' or 'import_path'"):
            CustomModelConfig(params={"model_id": "m"})

    def test_both_provider_and_import_path_rejected(self):
        with pytest.raises(ValidationError, match="only one of 'provider' or 'import_path'"):
            CustomModelConfig(provider="openai", import_path="a.B")


# ---------------------------------------------------------------------------
# SummarizingConfig — exclusividad de campos
# ---------------------------------------------------------------------------


class TestSummarizingConfig:
    """SCH-C01"""

    def test_si_ambos_campos_presentes_lanza_error(self):
        """SCH-C01: agent + prompt simultáneos → ValidationError (campos mutuamente exclusivos)"""
        from pydantic import ValidationError

        agent = SummarizationAgentConfig()
        with pytest.raises(ValidationError, match="mutually exclusive"):
            SummarizingConfig(
                summarization_agent=agent,
                summarization_system_prompt="Resume esto",
            )

    def test_solo_prompt_se_conserva(self):
        """Bonus: solo prompt sin agent → se conserva"""
        config = SummarizingConfig(summarization_system_prompt="Resume esto")
        assert config.summarization_system_prompt == "Resume esto"

    def test_solo_agent_se_conserva(self):
        """Bonus: solo agent sin prompt → se conserva"""
        agent = SummarizationAgentConfig()
        config = SummarizingConfig(summarization_agent=agent)
        assert config.summarization_agent is not None
        assert config.summarization_system_prompt is None


# ---------------------------------------------------------------------------
# LoomConfig — defaults y alias
# ---------------------------------------------------------------------------


class TestLoomConfig:
    """SCH-L01 a SCH-L02"""

    def test_default_workspace_name_es_warp(self):
        """SCH-L01: sin argumentos → workspace_name='warp'"""
        config = LoomConfig()
        assert config.workspace_name == "warp"

    def test_alias_name_funciona_en_model_validate(self):
        """SCH-L02: campo 'name' en el dict se mapea a workspace_name"""
        config = LoomConfig.model_validate({"name": "mi_proyecto"})
        assert config.workspace_name == "mi_proyecto"

    def test_populate_by_name_permite_usar_nombre_real_como_kwarg(self):
        """Bonus: populate_by_name=True → LoomConfig(workspace_name=...) funciona"""
        config = LoomConfig(workspace_name="otro")
        assert config.workspace_name == "otro"

    def test_populate_by_name_permite_usar_nombre_real_en_model_validate(self):
        """Bonus: populate_by_name=True → model_validate con field name también funciona"""
        config = LoomConfig.model_validate({"workspace_name": "otro"})
        assert config.workspace_name == "otro"

    def test_extra_field_rechazado_por_extra_forbid(self):
        """Bonus: extra='forbid' → ValidationError con campo desconocido"""
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            LoomConfig(campo_desconocido="valor")


# ---------------------------------------------------------------------------
# AgentRequest / AgentResponse / AgentResponseMetadata — SCH-IO
# ---------------------------------------------------------------------------


class TestAgentRequest:
    """SCH-IO01 a SCH-IO08"""

    def test_query_string_simple(self):
        """SCH-IO01: query como string → válido"""
        req = AgentRequest(query="hola", session_id="s1", user_id="u1")
        assert req.query == "hola"

    def test_session_y_user_id_requeridos(self):
        """SCH-IO02: session_id y user_id tienen defaults vacíos → no lanza ValidationError"""
        req = AgentRequest(query="hola")
        assert req.session_id == ""
        assert req.user_id == ""

    def test_session_y_user_id_explicitos(self):
        """SCH-IO03: session_id y user_id provistos → se usan tal cual"""
        req = AgentRequest(query="hola", session_id="s-123", user_id="u-456")
        assert req.session_id == "s-123"
        assert req.user_id == "u-456"

    def test_query_string_strip_whitespace(self):
        """SCH-IO04: query string con espacios al inicio/fin → trim automático"""
        req = AgentRequest(query="  hola mundo  ", session_id="s1", user_id="u1")
        assert req.query == "hola mundo"

    def test_query_string_vacio_lanza_error(self):
        """SCH-IO05: query string vacío → ValidationError por min_length=1"""
        with pytest.raises(ValidationError):
            AgentRequest(query="", session_id="s1", user_id="u1")

    def test_query_complex_con_byte_source(self):
        """SCH-IO06: AgentComplexRequest con ByteSource → válido"""
        req = AgentRequest(
            session_id="s1",
            user_id="u1",
            query=AgentComplexRequest(
                format="pdf",
                name="doc.pdf",
                sources=ByteSource(bytes=b"%PDF-data"),
            ),
        )
        assert isinstance(req.query, AgentComplexRequest)
        assert isinstance(req.query.sources, ByteSource)

    def test_query_complex_con_s3_source(self):
        """SCH-IO07: AgentComplexRequest con SourceFileS3 → válido"""
        req = AgentRequest(
            session_id="s1",
            user_id="u1",
            query=AgentComplexRequest(
                format="png",
                name="imagen.png",
                sources=SourceFileS3(location=LocationS3(uri="s3://my-bucket/imagen.png")),
            ),
        )
        assert isinstance(req.query.sources, SourceFileS3)
        assert req.query.sources.location.uri == "s3://my-bucket/imagen.png"

    def test_location_s3_bucket_owner_alias(self):
        """SCH-IO08: LocationS3 acepta bucketOwner como alias de bucket_owner"""
        loc = LocationS3.model_validate({"uri": "s3://bucket/key", "bucketOwner": "123456789"})
        assert loc.bucket_owner == "123456789"

    def test_extras_vacio_por_defecto(self):
        """SCH-IO09b: extras es dict vacío por defecto"""
        req = AgentRequest(query="hola", session_id="s1", user_id="u1")
        assert req.extras == {}

    def test_extras_se_asignan(self):
        """SCH-IO09c: extras provistos → se conservan"""
        req = AgentRequest(
            query="hola",
            session_id="s1",
            user_id="u1",
            extras={"jwt": "token-abc", "tenant": "acme"},
        )
        assert req.extras["jwt"] == "token-abc"
        assert req.extras["tenant"] == "acme"


class TestAgentResponse:
    """SCH-IO09 a SCH-IO12"""

    def _make_metadata(self, **kwargs) -> AgentResponseMetadata:
        defaults = {
            "session_id": "s1",
            "user_id": "u1",
            "user_msg_idx": 0,
            "assistant_msg_idx": 1,
            "input_tokens": 10,
            "output_tokens": 20,
            "total_tokens": 30,
            "response_time_ms": 300.0,
            "model_id": "claude-3",
        }
        return AgentResponseMetadata(**{**defaults, **kwargs})

    def test_response_valido(self):
        """SCH-IO09: AgentResponse con answer y metadata → válido"""
        resp = AgentResponse(answer="respuesta", metadata=self._make_metadata())
        assert resp.answer == "respuesta"
        assert resp.metadata.total_tokens == 30

    def test_metadata_contiene_session_y_user(self):
        """SCH-IO09b: session_id y user_id viven en metadata"""
        meta = self._make_metadata(session_id="s-abc", user_id="u-xyz")
        assert meta.session_id == "s-abc"
        assert meta.user_id == "u-xyz"

    def test_metadata_tokens_de_strands(self):
        """SCH-IO10: AgentResponseMetadata refleja tokens de Strands accumulated_usage"""
        meta = self._make_metadata(input_tokens=100, output_tokens=50, total_tokens=150)
        assert meta.input_tokens == 100
        assert meta.output_tokens == 50
        assert meta.total_tokens == 150

    def test_metadata_tool_calls_vacio_por_defecto(self):
        """SCH-IO10b: tool_calls es lista vacía por defecto"""
        meta = self._make_metadata()
        assert meta.tool_calls == []

    def test_metadata_raw_metrics_opcional(self):
        """SCH-IO11: raw_metrics es opcional → None por defecto"""
        meta = self._make_metadata()
        assert meta.raw_metrics is None

    def test_metadata_sin_model_id_es_none(self):
        """SCH-IO12: model_id es opcional → None por defecto (agentes sin model en YAML)"""
        meta = AgentResponseMetadata(
            session_id="s1",
            user_id="u1",
            user_msg_idx=0,
            assistant_msg_idx=1,
            input_tokens=10,
            output_tokens=5,
            total_tokens=15,
            response_time_ms=100,
        )
        assert meta.model_id is None


def test_unknown_agent_key_names_the_field_and_suggests():
    from loom.schemas.config.agent import AgentConfig

    with pytest.raises(ValidationError, match=r"toolz.*tools"):
        AgentConfig.model_validate({"name": "x", "toolz": ["a"]})


def test_unknown_app_key_names_the_field():
    from loom.schemas.config.app import AppConfig

    with pytest.raises(ValidationError, match="regionn"):
        AppConfig.model_validate({"regionn": "us-east-1"})


def test_bidi_rejects_conversation():
    from loom.schemas.config.agent import AgentConfig

    with pytest.raises(ValidationError, match="conversation"):
        AgentConfig.model_validate({"name": "voice", "kind": "bidi", "conversation": "sliding"})


def test_example_and_new_agent_yaml_still_validate():
    from pathlib import Path

    import yaml
    from jinja2 import Environment

    from loom.schemas.config.agent import AgentConfig

    root = Path(__file__).resolve().parents[2]
    for path in (root / "examples").rglob("*.yml"):
        AgentConfig.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))

    template = (root / "src/loom/templates/new/config/{{folder_name}}.yml.j2").read_text(
        encoding="utf-8"
    )
    rendered = (
        Environment()
        .from_string(template)
        .render(
            agent={
                "name": "demo",
                "description": "d",
                "model": "default",
                "system_prompt": {"prompt": "prompt.md"},
                "retry": "low",
                "output": None,
            }
        )
    )
    AgentConfig.model_validate(yaml.safe_load(rendered))
