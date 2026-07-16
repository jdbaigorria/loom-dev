"""Tests for Loom built-in tools (``loom.builtins``).

Covers the factory contract (per-instance Strands tool name → no collision),
schema generation, runtime behaviour with mocked backends, and resolution
through the tool loader via the ``builtin.`` source.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from loom.builtins import BUILTIN_TOOLS, make_apicall, make_kb
from loom.builtins.apicall import _project
from loom.core.exceptions import ToolLoadError
from loom.core.loaders.tool import get_tools
from loom.schemas.config.tool import ToolConfig

_DIRS = (Path("/nonexistent/agent"), Path("/nonexistent/shared"))


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


class TestRegistry:
    def test_registry_expone_kb_y_apicall(self):
        """BLT-T01: el registry contiene las factories empaquetadas."""
        assert set(BUILTIN_TOOLS) == {"kb", "apicall"}


# ---------------------------------------------------------------------------
# apicall
# ---------------------------------------------------------------------------


class TestApiCall:
    def test_tool_name_es_el_name_pasado_no_call(self):
        """BLT-T02: el nombre Strands es el `name`, no el de la función ('call')."""
        tool = make_apicall(name="weather_api", base_url="https://x.com", allowed_paths=["/v1/*"])
        assert tool.tool_name == "weather_api"

    def test_dos_instancias_no_colisionan_en_el_registry(self):
        """BLT-T03: dos apicall con names distintos se montan juntos sin chocar."""
        # Deliberate direct import: this test pins Strands' own dedup contract
        # (register_tool raises on duplicate names), the very thing the factory
        # rename defends against. Not application code, so the ACL rule is waived.
        from strands.tools.registry import ToolRegistry  # noqa: TID251

        a = make_apicall(name="weather_api", base_url="https://a.com", allowed_paths=["/v1/*"])
        b = make_apicall(name="billing_api", base_url="https://b.com", allowed_paths=["/inv/*"])
        reg = ToolRegistry()
        reg.process_tools([a, b])
        assert set(reg.registry) == {"weather_api", "billing_api"}

    def test_schema_tiene_los_parametros_esperados(self):
        """BLT-T04: el inputSchema expone path/method/body/params con descripción."""
        tool = make_apicall(name="svc", base_url="https://x.com", allowed_paths=["/v1/*"])
        props = tool.tool_spec["inputSchema"]["json"]["properties"]
        assert set(props) == {"path", "method", "body", "params"}
        assert "Request path" in props["path"]["description"]

    def test_path_fuera_de_allowlist_devuelve_error_sin_request(self):
        """BLT-T05: path no permitido → ToolResult error y no se hace request."""
        tool = make_apicall(name="svc", base_url="https://x.com", allowed_paths=["/ok/*"])
        with patch("requests.Session.request") as mock_req:
            result = tool(path="/secret/data")
        assert result["status"] == "error"
        assert "not allowed" in result["content"][0]["text"]
        mock_req.assert_not_called()

    def test_path_permitido_hace_request_y_limpia_respuesta(self):
        """BLT-T06: path permitido → request + ToolResult success con json limpio."""
        tool = make_apicall(name="svc", base_url="https://x.com", allowed_paths=["/ok/*"])
        resp = MagicMock()
        resp.json.return_value = {"a": 1, "b": "", "c": None}
        resp.raise_for_status.return_value = None
        with patch("requests.Session.request", return_value=resp) as mock_req:
            result = tool(path="/ok/items", method="GET", params={"q": "x"})
        assert result["status"] == "success"
        assert result["content"][0]["json"] == {"a": 1}  # _clean_dict dropped "" and None
        mock_req.assert_called_once()

    def test_allowed_paths_vacio_es_error(self):
        """BLT-T07: una tool HTTP sin allow-list es insegura → ValueError."""
        with pytest.raises(ValueError, match="allowed_paths"):
            make_apicall(name="svc", base_url="https://x.com", allowed_paths=[])


# ---------------------------------------------------------------------------
# apicall — domain mode (bind / expose)
# ---------------------------------------------------------------------------


def _pokemon_tool():
    return make_apicall(
        name="get_pokemon",
        description="Fetch a Pokémon by name or id.",
        bind={
            "base_url": "https://pokeapi.co/api/v2",
            "path": "/pokemon/{name_or_id}",
            "method": "GET",
        },
        expose={
            "name_or_id": {"type": "string", "required": True, "description": "Name or id."},
        },
    )


class TestApiCallDomain:
    def test_expose_se_compila_al_inputschema_del_modelo(self):
        """BLT-T17: el modelo ve el schema de dominio, no path/method/body/params."""
        tool = _pokemon_tool()
        assert tool.tool_name == "get_pokemon"
        props = tool.tool_spec["inputSchema"]["json"]["properties"]
        assert set(props) == {"name_or_id"}
        assert tool.tool_spec["inputSchema"]["json"]["required"] == ["name_or_id"]
        assert tool.tool_spec["description"] == "Fetch a Pokémon by name or id."

    def test_el_framework_arma_el_path_desde_la_plantilla(self):
        """BLT-T18: {name_or_id} se inyecta en la URL; el modelo no elige el path."""
        tool = _pokemon_tool()
        resp = MagicMock()
        resp.json.return_value = {"name": "ivysaur"}
        resp.raise_for_status.return_value = None
        with patch("requests.Session.request", return_value=resp) as mock_req:
            result = tool(name_or_id="ivysaur")
        assert result["status"] == "success"
        assert mock_req.call_args.kwargs["url"] == "https://pokeapi.co/api/v2/pokemon/ivysaur"
        assert mock_req.call_args.kwargs["method"] == "GET"

    def test_param_de_path_se_urlencodea_y_no_escapa_segmento(self):
        """BLT-T19: un '/' en el valor se codifica, no agrega segmento de path."""
        tool = _pokemon_tool()
        resp = MagicMock()
        resp.json.return_value = {}
        resp.raise_for_status.return_value = None
        with patch("requests.Session.request", return_value=resp) as mock_req:
            tool(name_or_id="a/b c")
        assert mock_req.call_args.kwargs["url"].endswith("/pokemon/a%2Fb%20c")

    def test_param_de_path_con_traversal_es_rechazado_sin_request(self):
        """BLT-T20: '..' en un segmento de path → error y no se hace request."""
        tool = _pokemon_tool()
        with patch("requests.Session.request") as mock_req:
            result = tool(name_or_id="../admin")
        assert result["status"] == "error"
        assert "Invalid request" in result["content"][0]["text"]
        mock_req.assert_not_called()

    def test_placeholders_en_query_y_body_para_post(self):
        """BLT-T21: {param} se rellena en body y query; el body solo va en writes."""
        tool = make_apicall(
            name="create_ticket",
            description="Open a ticket.",
            bind={
                "base_url": "https://api.x.com",
                "path": "/tickets",
                "method": "POST",
                "query": {"trace": "{trace}"},
                "body": {"id": "{id}", "priority": "{priority}"},
            },
            expose={
                "id": {"type": "string", "required": True, "description": "Employee ID."},
                "priority": {"type": "string", "default": "normal", "description": "Prio."},
                "trace": {"type": "string", "required": True, "description": "Trace id."},
            },
        )
        resp = MagicMock()
        resp.json.return_value = {"id": 1}
        resp.raise_for_status.return_value = None
        with patch("requests.Session.request", return_value=resp) as mock_req:
            tool(id="123", trace="t1")  # priority omitido → usa default
        kw = mock_req.call_args.kwargs
        assert kw["json"] == {"id": "123", "priority": "normal"}
        assert kw["params"] == {"trace": "t1"}

    def test_whole_placeholder_preserva_el_tipo(self):
        """BLT-T22: un body "{n}" entero llega como int, no como string."""
        tool = make_apicall(
            name="set_count",
            description="Set count.",
            bind={
                "base_url": "https://api.x.com",
                "path": "/count",
                "method": "POST",
                "body": {"n": "{n}"},
            },
            expose={"n": {"type": "integer", "required": True, "description": "Count."}},
        )
        resp = MagicMock()
        resp.json.return_value = {}
        resp.raise_for_status.return_value = None
        with patch("requests.Session.request", return_value=resp) as mock_req:
            tool(n=42)
        assert mock_req.call_args.kwargs["json"] == {"n": 42}

    def test_omit_if_default_descarta_la_key_cuando_queda_en_el_default(self):
        """BLT-T22b: omit_if_default deja la key fuera del request cuando vale el default.

        Espeja una tool Python a mano (`if nro_doc: payload[...]=nro_doc`): un param
        no provisto no debe mandarse como `0`/`""`, que el backend podría tratar como
        un filtro real en vez de "campo ausente".
        """
        tool = make_apicall(
            name="get_orders",
            description="List orders.",
            bind={
                "base_url": "https://api.x.com",
                "path": "/orders",
                "method": "POST",
                "body": {"limit": 5, "nroDoc": "{nro_doc}", "estado": "{estado}"},
            },
            expose={
                "nro_doc": {
                    "type": "integer",
                    "default": 0,
                    "omit_if_default": True,
                    "description": "Doc number.",
                },
                "estado": {"type": "integer", "default": 1, "description": "State."},
            },
        )
        resp = MagicMock()
        resp.json.return_value = {}
        resp.raise_for_status.return_value = None
        with patch("requests.Session.request", return_value=resp) as mock_req:
            tool()  # nada provisto → nro_doc queda en su default y se omite
        assert mock_req.call_args.kwargs["json"] == {"limit": 5, "estado": 1}

    def test_omit_if_default_envia_la_key_cuando_difiere_del_default(self):
        """BLT-T22c: con un valor distinto del default, la key sí se envía."""
        tool = make_apicall(
            name="get_orders",
            description="List orders.",
            bind={
                "base_url": "https://api.x.com",
                "path": "/orders",
                "method": "POST",
                "body": {"nroDoc": "{nro_doc}"},
            },
            expose={
                "nro_doc": {
                    "type": "integer",
                    "default": 0,
                    "omit_if_default": True,
                    "description": "Doc number.",
                },
            },
        )
        resp = MagicMock()
        resp.json.return_value = {}
        resp.raise_for_status.return_value = None
        with patch("requests.Session.request", return_value=resp) as mock_req:
            tool(nro_doc=99)
        assert mock_req.call_args.kwargs["json"] == {"nroDoc": 99}

    def test_omit_if_default_sin_default_es_error_en_build(self):
        """BLT-T22d: omit_if_default sin un default declarado → error en build."""
        with pytest.raises(ValueError, match="without a 'default'"):
            make_apicall(
                name="x",
                description="d",
                bind={"base_url": "https://x.com", "path": "/a", "body": {"q": "{q}"}},
                expose={"q": {"type": "string", "omit_if_default": True, "description": "q"}},
            )

    def test_omit_if_default_en_path_param_es_error_en_build(self):
        """BLT-T22e: omit_if_default sobre un path param → error en build."""
        with pytest.raises(ValueError, match="cannot set 'omit_if_default'"):
            make_apicall(
                name="x",
                description="d",
                bind={"base_url": "https://x.com", "path": "/a/{id}"},
                expose={
                    "id": {
                        "type": "string",
                        "required": True,
                        "default": "x",
                        "omit_if_default": True,
                        "description": "id",
                    }
                },
            )

    def test_modo_dominio_sin_description_es_error(self):
        """BLT-T23: la descripción es el contrato con el modelo → obligatoria."""
        with pytest.raises(ValueError, match="requires a 'description'"):
            make_apicall(
                name="x",
                bind={"base_url": "https://x.com", "path": "/a"},
                expose={},
            )

    def test_placeholder_no_declarado_en_expose_es_error(self):
        """BLT-T24: {param} usado en bind pero ausente en expose → error en build."""
        with pytest.raises(ValueError, match="not declared in expose"):
            make_apicall(
                name="x",
                description="d",
                bind={"base_url": "https://x.com", "path": "/a/{missing}"},
                expose={},
            )

    def test_param_de_path_no_required_es_error(self):
        """BLT-T25: un segmento de path opcional produciría URLs inválidas → error."""
        with pytest.raises(ValueError, match="must be 'required: true'"):
            make_apicall(
                name="x",
                description="d",
                bind={"base_url": "https://x.com", "path": "/a/{id}"},
                expose={"id": {"type": "string", "description": "id"}},
            )

    def test_type_de_expose_invalido_es_error(self):
        """BLT-T26: un type fuera de los JSON types válidos → error en build."""
        with pytest.raises(ValueError, match="is invalid"):
            make_apicall(
                name="x",
                description="d",
                bind={"base_url": "https://x.com", "path": "/a/{id}"},
                expose={"id": {"type": "uuid", "required": True, "description": "id"}},
            )

    def test_declarar_ambos_modos_es_error(self):
        """BLT-T27: domain (bind/expose) y generic (allowed_paths) son excluyentes."""
        with pytest.raises(ValueError, match="not both"):
            make_apicall(
                name="x",
                description="d",
                bind={"base_url": "https://x.com", "path": "/a/{id}"},
                expose={"id": {"type": "string", "required": True, "description": "id"}},
                allowed_paths=["/a/*"],
            )

    def test_select_proyecta_la_respuesta_y_descarta_el_resto(self):
        """BLT-T29: select recorta el payload (top-level y path con punto)."""
        tool = make_apicall(
            name="get_pokemon",
            description="Fetch a Pokémon.",
            bind={
                "base_url": "https://pokeapi.co/api/v2",
                "path": "/pokemon/{name_or_id}",
                "method": "GET",
                "select": ["id", "name", "sprites.front_default"],
            },
            expose={"name_or_id": {"type": "string", "required": True, "description": "id"}},
        )
        resp = MagicMock()
        resp.json.return_value = {
            "id": 2,
            "name": "ivysaur",
            "moves": [{"x": 1}] * 100,  # el bulk que infla el contexto
            "sprites": {"front_default": "url.png", "back_default": "back.png"},
        }
        resp.raise_for_status.return_value = None
        with patch("requests.Session.request", return_value=resp):
            result = tool(name_or_id="ivysaur")
        data = result["content"][0]["json"]
        assert data == {"id": 2, "name": "ivysaur", "sprites": {"front_default": "url.png"}}
        assert "moves" not in data

    def test_input_validation_del_agente_acepta_los_params_expuestos(self):
        """BLT-T31: el modelo de validación de Strands (firma) acepta los expose.

        El agente valida el input contra un modelo derivado de la firma de la
        función antes de llamarla; un runner `**kwargs` pelado lo rompería.
        """
        tool = _pokemon_tool()
        assert set(tool.tool_spec["inputSchema"]["json"]["properties"]) == {"name_or_id"}
        # validate_input es el paso que corre el event loop antes de ejecutar la tool.
        validated = tool._metadata.validate_input({"name_or_id": "ivysaur"})
        assert validated == {"name_or_id": "ivysaur"}

    def test_select_invalido_es_error_en_build(self):
        """BLT-T30: select que no es lista de strings → error en build."""
        with pytest.raises(ValueError, match="select must be a list of strings"):
            make_apicall(
                name="x",
                description="d",
                bind={"base_url": "https://x.com", "path": "/a", "select": "id"},
                expose={},
            )

    def test_select_proyecta_dentro_de_listas_anidadas(self):
        """BLT-T29b: un path que atraviesa una lista proyecta cada item.

        Regresión: antes `_project` devolvía {} (vaciaba la respuesta) en cuanto el
        path tocaba una lista — el shape típico de paginación `{"body": [...]}`.
        """
        data = {"body": [{"codigo": 1, "descripcion": "BUENOS AIRES", "extra": "x"}]}
        assert _project(data, ["body.codigo", "body.descripcion"]) == {
            "body": [{"codigo": 1, "descripcion": "BUENOS AIRES"}]
        }

    def test_select_renombra_la_hoja(self):
        """BLT-T29c: sufijo `:dst` renombra el campo hoja, también dentro de listas."""
        data = {"body": [{"codigo": 1, "descripcion": "x"}]}
        assert _project(data, ["body.codigo:body.id", "body.descripcion:body.nombre"]) == {
            "body": [{"id": 1, "nombre": "x"}]
        }

    def test_select_sobre_lista_en_la_raiz(self):
        """BLT-T29d: una lista en la raíz también se proyecta por item."""
        data = [{"codigo": 1, "extra": "x"}, {"codigo": 2, "extra": "y"}]
        assert _project(data, ["codigo"]) == [{"codigo": 1}, {"codigo": 2}]

    def test_select_dict_anidado_sigue_funcionando(self):
        """BLT-T29e: el caso dict-anidado (sin listas) no cambia de comportamiento."""
        data = {"id": 2, "name": "ivysaur", "sprites": {"front_default": "u", "back": "b"}}
        assert _project(data, ["id", "name", "sprites.front_default"]) == {
            "id": 2,
            "name": "ivysaur",
            "sprites": {"front_default": "u"},
        }

    def test_select_rename_con_distinta_profundidad_es_error_en_build(self):
        """BLT-T30b: un rename que cambia la profundidad del path → error en build."""
        with pytest.raises(ValueError, match="same nesting depth"):
            make_apicall(
                name="x",
                description="d",
                bind={
                    "base_url": "https://x.com",
                    "path": "/a",
                    "select": ["body.codigo:id"],
                },
                expose={},
            )

    def test_enum_se_propaga_al_schema(self):
        """BLT-T28: enum declarado en expose aparece en el inputSchema."""
        tool = make_apicall(
            name="x",
            description="d",
            bind={"base_url": "https://x.com", "path": "/a", "method": "GET", "query": {"k": "{k}"}},
            expose={"k": {"type": "string", "enum": ["a", "b"], "description": "k"}},
        )
        assert tool.tool_spec["inputSchema"]["json"]["properties"]["k"]["enum"] == ["a", "b"]


# ---------------------------------------------------------------------------
# kb
# ---------------------------------------------------------------------------


def _kb_response(*results):
    return {"retrievalResults": list(results)}


def _hit(score, text):
    return {"score": score, "content": {"text": text}, "location": {"type": "S3"}}


class TestKb:
    def test_name_por_defecto_y_descripcion_dinamica(self):
        """BLT-T08: name default 'kb_search' y la descripción lista los kb_ids."""
        with patch("boto3.client"):
            tool = make_kb(kb_ids=["docs", "tickets"])
        assert tool.tool_name == "kb_search"
        assert "docs" in tool.tool_spec["description"]
        assert "tickets" in tool.tool_spec["description"]

    def test_kb_id_invalido_devuelve_error(self):
        """BLT-T09: kb_id no configurado → ToolResult error."""
        with patch("boto3.client"):
            tool = make_kb(kb_ids=["docs"])
        result = tool(query="hola", kb_id="nope")
        assert result["status"] == "error"
        assert "Unknown kb_id" in result["content"][0]["text"]

    def test_fan_out_mergea_y_reordena_por_score_con_threshold(self):
        """BLT-T10: busca en todos los KB, filtra por score y reordena por relevancia."""
        client = MagicMock()
        client.retrieve.side_effect = [
            _kb_response(_hit(0.9, "A"), _hit(0.5, "B")),  # B < threshold 0.7 → fuera
            _kb_response(_hit(0.8, "C")),
        ]
        with patch("boto3.client", return_value=client):
            tool = make_kb(kb_ids=["docs", "tickets"], score_threshold=0.7, top_k=5)
        result = tool(query="q")
        passages = result["content"][1]["json"]["passages"]
        assert [p["text"] for p in passages] == ["A", "C"]  # 0.9 luego 0.8, B filtrado
        assert passages[0]["kb_id"] == "docs"
        assert passages[1]["kb_id"] == "tickets"

    def test_top_k_trunca_resultados(self):
        """BLT-T11: top_k limita la cantidad final tras el merge."""
        client = MagicMock()
        client.retrieve.side_effect = [
            _kb_response(_hit(0.9, "A")),
            _kb_response(_hit(0.8, "C")),
        ]
        with patch("boto3.client", return_value=client):
            tool = make_kb(kb_ids=["docs", "tickets"], top_k=1)
        passages = tool(query="q")["content"][1]["json"]["passages"]
        assert len(passages) == 1 and passages[0]["text"] == "A"

    def test_search_type_invalido_es_error(self):
        """BLT-T12: search_type fuera de HYBRID/SEMANTIC → ValueError."""
        with pytest.raises(ValueError, match="search_type"):
            make_kb(kb_ids=["docs"], search_type="MAGIC")

    def test_kb_ids_vacio_es_error(self):
        """BLT-T13: kb_ids vacío → ValueError."""
        with pytest.raises(ValueError, match="kb_ids"):
            make_kb(kb_ids=[])

    def test_boto_session_none_usa_boto3_client_ambiente(self):
        """Sin boto_session, arma el cliente con la cadena de credenciales default."""
        with patch("boto3.client") as client_cls:
            make_kb(kb_ids=["docs"], region="us-east-1")
        client_cls.assert_called_once_with("bedrock-agent-runtime", region_name="us-east-1")

    def test_boto_session_dado_construye_cliente_desde_la_session(self):
        """Con boto_session, el cliente sale de esa session (no de boto3 ambiente)."""
        session = MagicMock()
        with patch("boto3.client") as client_cls:
            make_kb(kb_ids=["docs"], region="us-east-1", boto_session=session)
        client_cls.assert_not_called()
        session.client.assert_called_once_with("bedrock-agent-runtime", region_name="us-east-1")


# ---------------------------------------------------------------------------
# Loader integration (source == "builtin")
# ---------------------------------------------------------------------------


class TestLoaderBuiltin:
    def test_get_tools_resuelve_builtin_desde_el_registry(self):
        """BLT-T14: una ToolConfig builtin se resuelve sin tocar el filesystem."""
        cfg = ToolConfig.model_validate(
            {
                "builtin.apicall": {
                    "name": "svc",
                    "base_url": "https://x.com",
                    "allowed_paths": ["/v1/*"],
                }
            }
        )
        tools = get_tools([cfg], *_DIRS)
        assert len(tools) == 1
        assert tools[0].tool_name == "svc"

    def test_builtin_inexistente_lanza_toolloaderror(self):
        """BLT-T15: nombre de builtin desconocido → ToolLoadError con tip."""
        cfg = ToolConfig.model_validate({"builtin.nope": {"x": 1}})
        with pytest.raises(ToolLoadError, match="Builtin tool 'nope' not found"):
            get_tools([cfg], *_DIRS)

    def test_builtin_con_params_invalidos_lanza_toolloaderror(self):
        """BLT-T16: params inválidos de la factory se envuelven en ToolLoadError."""
        cfg = ToolConfig.model_validate({"builtin.apicall": {"name": "svc", "allowed_paths": []}})
        with pytest.raises(ToolLoadError, match="Failed to build builtin 'apicall'"):
            get_tools([cfg], *_DIRS)

    def test_overlay_llega_al_builtin_que_lo_declara(self):
        """El overlay (ej. boto_session) se ofrece a un builtin que lo acepta, como kb."""
        session = MagicMock()
        cfg = ToolConfig.model_validate({"builtin.kb": {"kb_ids": ["docs"]}})
        with patch("boto3.client") as client_cls:
            get_tools([cfg], *_DIRS, overlay={"boto_session": session})
        client_cls.assert_not_called()
        session.client.assert_called_once()

    def test_overlay_se_ignora_en_builtin_que_no_lo_declara(self):
        """apicall no tiene parametro boto_session: el overlay no le rompe la llamada."""
        cfg = ToolConfig.model_validate(
            {"builtin.apicall": {"name": "svc", "base_url": "https://x.com", "allowed_paths": ["/v1/*"]}}
        )
        tools = get_tools([cfg], *_DIRS, overlay={"boto_session": MagicMock()})
        assert len(tools) == 1
        assert tools[0].tool_name == "svc"
