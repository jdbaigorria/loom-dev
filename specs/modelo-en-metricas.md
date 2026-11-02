# Especificación: el modelo y su configuración en las métricas (L6)

| | |
|---|---|
| **Estado** | Propuesta |
| **Fecha** | 2026-11-02 |
| **Origen** | HostOrg (`host-agentics`): con las métricas de L5 se ve cuánto tarda cada agente, pero no qué modelo ni con qué configuración. Al cambiar el modelo o un parámetro, el antes y el después quedan mezclados bajo el mismo `agent`. |
| **Depende de** | L2 (`TurnMetrics`) y L5 (hook `metrics`) de [`observabilidad-del-turno.md`](observabilidad-del-turno.md) y [`hook-de-metricas.md`](hook-de-metricas.md) |
| **Relacionado** | Weave [`weave-modelo-en-turno.md`](../../weave-dev/specs/weave-modelo-en-turno.md) (W14), que consume `describe_model` y `variant_of` |

---

## 1. Motivación

Para comparar modelos hacen falta dos cosas que hoy no salen:

1. **Qué modelo respondió.** Con un modelo fijo es `model.config["model_id"]`. Con `fallback` o `route`, es el candidato que contestó, y puede cambiar turno a turno.
2. **Con qué configuración.** `max_tokens`, `effort`, `thinking`, `streaming`, etc. Cada proveedor la guarda en un lugar distinto: Bedrock en el `config` y en `additional_request_fields`, OpenAI en `params`, Anthropic directo en los dos.

Y, para experimentos, una forma de separar dos configuraciones del mismo modelo: la **variante**.

### 1.1 Decisiones tomadas

| Tema | Decisión |
|---|---|
| Modelo | **Dimensión** `model`, con el id tal cual (`us.anthropic.claude-haiku-5-5`): el prefijo es el perfil de inferencia y cambia la latencia |
| Configuración | **Propiedades**, nunca dimensiones: cada combinación sería una métrica facturada aparte |
| Nombres | **Normalizados**, iguales para todos los proveedores, para agrupar con una sola consulta |
| Lista | **Blanca** (deny by default): lo que no está en §2 no sale |
| Guardrail | Solo `guardrail: true/false`, sin id ni versión |
| Config del agente | **No** (`version` del YAML, nombre del perfil): no aportan para comparar modelos |
| Variante | Label `metrics.variant` del agente, como dimensión opcional |

---

## 2. Lista blanca: `ModelSettings`

```python
class ModelSettings(BaseModel, frozen=True):
    max_tokens: int | None = None
    temperature: float | None = None
    top_p: float | None = None
    top_k: int | None = None
    streaming: bool | None = None
    effort: str | None = None
    thinking: str | None = None
    thinking_budget: int | None = None
    service_tier: str | None = None
    prompt_cache: bool | None = None
    guardrail: bool | None = None
```

De dónde sale cada campo. `cfg` es `model.config` (o `model.get_config()`), `p` es `cfg["params"]` y `arf` es `cfg["additional_request_fields"]`. Se toma el primer valor presente, en el orden de la columna:

| Campo | Fuentes, en orden |
|---|---|
| `max_tokens` | `cfg.max_tokens`, `p.max_tokens`, `p.max_completion_tokens` |
| `temperature` | `cfg.temperature`, `p.temperature` |
| `top_p` | `cfg.top_p`, `p.top_p` |
| `top_k` | `arf.top_k`, `p.top_k` |
| `streaming` | `cfg.streaming`, `cfg.stream`, `p.stream` |
| `effort` | `arf.output_config.effort`, `p.reasoning_effort`, `arf.reasoningConfig.maxReasoningEffort` |
| `thinking` | `arf.thinking.type`, `arf.reasoningConfig.type` |
| `thinking_budget` | `arf.thinking.budget_tokens` |
| `service_tier` | `cfg.service_tier`, `p.service_tier` |
| `prompt_cache` | `true` si hay `cfg.cache_config`, `cfg.cache_prompt` o un bloque `cachePoint` en `agent.system_prompt_content`; si no, `false` |
| `guardrail` | `true` si `cfg.guardrail_id` tiene valor; si no, `false` |

Reglas:

- **Tipos estrictos.** Un valor que no es del tipo del campo (por ejemplo un dict donde se espera `str`) queda en `None`. Nunca se hace `str()` de un objeto arbitrario.
- **Ausente es `None`**, no un default inventado. `streaming: None` significa que el proveedor usa su default, no que es `false`.
- **Excluido siempre**, aunque esté en el config: `boto_session`, `boto_client_config`, `client_args`, `api_key`, headers, `additional_args`, `stop_sequences`, `guardrail_id`/`guardrail_version` (solo el booleano), `include_tool_result_status`, `strict_tools`, `use_native_token_count`, `additional_response_field_paths`, y cualquier otra clave de `params` o de `additional_request_fields`.
- **Agregar un campo** a la lista es un cambio de Loom, con test. No hay forma de configurarla desde el YAML: una lista configurable deja de ser una lista blanca.

---

## 3. Spec

| # | Spec | Depende de | Rompe compatibilidad |
|---|---|---|---|
| L6 | Modelo, configuración y variante en `TurnContext` y en los sinks del hook `metrics` | L2, L5 | No: agrega campos y un conjunto de dimensiones |

---

## L6. Modelo, configuración y variante

### API pública (`loom.metrics`)

```python
class ModelDescription(BaseModel, frozen=True):
    model_id: str | None
    settings: ModelSettings
    fallbacks: int = 0          # intentos fallidos antes del que respondió (router)

def describe_model(agent) -> ModelDescription: ...
def variant_of(agent) -> str | None: ...
```

- **`describe_model`** lee el modelo del agente construido. Si el modelo es un `ModelRouter`, toma el candidato que respondió en el último turno según `_loom_routing_trace` (el último intento con `outcome == "OK"`), su `model_id` y la configuración de **ese** modelo. `fallbacks` cuenta los intentos fallidos de ese turno. Si el router no llegó a responder (el turno falló), devuelve el primer candidato y `fallbacks` = intentos fallidos. Para eso, `RoutingTraceHook` guarda también la referencia al modelo de cada intento, no solo el id.
- **`variant_of`** devuelve el label `metrics.variant` del agente. El builder deja los labels en el agente (`agent._loom_labels`, igual que `_loom_routing_trace`). Solo acepta escalares (`str`, `int`, `bool` → `str`). Una lista da `None`, y el builder loguea un WARNING al construir.
- Ninguna de las dos lanza: ante algo inesperado devuelven `ModelDescription(model_id=None, settings=ModelSettings())` o `None`.
- `ModelSettings`, `ModelDescription`, `describe_model` y `variant_of` se exportan desde `loom`, como `TurnMetrics`.

### `TurnContext`

Suma:

```python
model_id: str | None = None
model_settings: ModelSettings | None = None
model_fallbacks: int = 0
variant: str | None = None
```

El hook los arma en `_emit` con `describe_model(event.agent)` y `variant_of(event.agent)`. **Orden:** el `RoutingTraceHook` se registra después de los hooks del usuario y los `After*` corren en orden inverso, así que registra los intentos antes de que `metrics` emita. Un test lo fija.

### Sink `emf`

La línea de `invocation` + `breakdown` declara varios conjuntos de dimensiones en la misma línea (EMF lo permite: cada conjunto es una agregación):

```json
"Dimensions": [
  ["agent", "service"],
  ["agent", "model", "service"],
  ["agent", "variant", "service"]
]
```

- `["agent", "model", …]` solo si hay `model_id`. `["agent", "variant", …]` solo si hay variante.
- El primer conjunto no cambia: los dashboards por agente que ya existen siguen andando.
- La línea de `tools` no cambia de dimensiones: la latencia de una tool no depende del modelo. Suma `model` y `variant` como propiedades.
- Propiedades nuevas en todas las líneas: `model` (también es la raíz de la dimensión), `model_config` (objeto con los campos de `ModelSettings` que no son `None`), `model_fallbacks` y `variant`.
- **Costo:** cada conjunto extra multiplica las series de esa línea. Con un modelo por agente y sin variante, pasa de 1 a 2 series por métrica de turno.

### Sink `log`

El `extra["context"]` ya lleva todo `TurnContext`, así que trae los campos nuevos sin cambios. El mensaje suma `model=%s`.

### Sink `modulo:funcion`

Recibe el `TurnContext` ampliado. No cambia la firma.

### Tests

- **`describe_model`, Bedrock:** `cfg` con `max_tokens`, `streaming: false`, `additional_request_fields: {thinking: {type: enabled, budget_tokens: 2048}, output_config: {effort: low}, anthropic_beta: [...]}`, `boto_session` y `guardrail_id`. Sale `ModelSettings(max_tokens=…, streaming=False, thinking="enabled", thinking_budget=2048, effort="low", guardrail=True)`, y ni `anthropic_beta` ni `boto_session` ni el id del guardrail aparecen en `model_dump()`.
- **`describe_model`, estilo OpenAI:** `cfg = {model_id, params: {max_completion_tokens, temperature, reasoning_effort, api_key}}`. Mapea los tres primeros y nunca expone `api_key`.
- **Tipos:** `effort: {"x": 1}` da `None`. `temperature: "0.2"` da `None`.
- **`prompt_cache`:** es `true` con un `cachePoint` en el system prompt y sin `cache_config`.
- **Router:** dos candidatos, falla el primero. `model_id` es el segundo, `fallbacks == 1` y `settings` son las del segundo.
- **`variant_of`:** con un label escalar, la lista y su warning, y sin label.
- **EMF:** con modelo y variante, tres conjuntos de dimensiones, y cada clave de dimensión en la raíz. Sin variante, dos. Sin modelo (`describe_model` falla), uno. La línea de tools mantiene `["agent", "tool", …]` y suma las propiedades.
- **Orden de hooks:** con un `fallback` real y `MockModel`s (el primero lanza), el `TurnContext` que recibe el sink tiene el modelo que respondió.

### Docs

- `docs/guides/observability.md`, "Metrics hook": tabla de `ModelSettings` con las fuentes, cómo funciona la variante y el costo de los conjuntos de dimensiones.
- `docs/guides/agents.md` (labels): `metrics.variant`.

---

## 4. Fuera de alcance

- Datos de la config del agente (`version`, nombre del perfil): se decidió no publicarlos.
- Modelo por ciclo: con router, cada ciclo podría usar otro candidato. `ModelCall` no lo registra todavía; se suma si hace falta.
- `region` del cliente: no está en `model.config` y requiere leer el cliente boto.
