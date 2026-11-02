# Especificación: observabilidad del turno (nivel de log, métricas por turno y puntos de debug)

| | |
|---|---|
| **Estado** | Propuesta |
| **Fecha** | 2026-10-28 |
| **Origen** | HostOrg (`host-agentics`): el `log_level` de `app.yml` no hace nada y las métricas por turno viven en el producto |
| **Relacionado** | Weave [`weave-metricas-de-turno.md`](../../weave-dev/specs/weave-metricas-de-turno.md) (W5–W8) y [`weave-debug-del-turno.md`](../../weave-dev/specs/weave-debug-del-turno.md) (W10–W12), que consumen L2 |

---

## 1. Motivación

Tres problemas que salieron de poner un agente en Lambda:

1. **`log_level` en `app.yml` no tiene efecto.** El schema lo valida ([schemas/config/app.py:29](../src/loom/schemas/config/app.py#L29)) pero el único que lo lee es el wizard de `loom init`. Quien escribe `log_level: DEBUG` espera ver el debug de Loom y no ve nada.
2. **Las métricas del turno las arma cada producto.** Strands entrega `result.metrics.get_summary()` en crudo. Para saber cuánto tardó el modelo, cuánto cada tool y en qué ciclo, HostOrg escribió ~200 líneas sobre las trazas (`internal/metrics_helpers.py`: `ciclos_del_turno`, `demoras_por_id`, `duraciones_de_tools`, `errores_de_tools`). Nada de eso es de HostOrg: son lecturas de la estructura de Strands, y se rompen igual en cualquier producto cuando Strands cambia la forma de las trazas.
3. **No hay puntos de debug durante el turno.** Loom tiene ~60 `logger.debug`, casi todos en la carga (config, hooks, tools, modelo): salen una vez por cold start. Durante el turno no se loguea nada salvo que el agente declare los hooks `logging` o `tool_tracker`, y aun así no se ve el modelo, los reintentos ni el recorte de la conversación.

### 1.1 El resumen de Strands es acumulativo

`EventLoopMetrics` vive en el `Agent`: `traces`, `tool_usage`, `cycle_count` y `total_duration` suman todos los turnos que corrió esa instancia. Hay dos casos:

- **Agente construido por turno** (Weave en Lambda: build → invoke → teardown). El resumen es del turno.
- **Agente reutilizado** (el REPL de `loom.dev`, cualquier backend que lo mantenga vivo). El resumen mezcla turnos. `run_and_record` lo guarda así en `.loom/stats/*.jsonl` y `loom agent stats` agrega sobre números ya acumulados.

`agent_invocations[-1]` sí es del último turno, pero solo trae uso de tokens, no tiempos.

---

## 2. Specs

| # | Spec | Depende de | Rompe compatibilidad |
|---|---|---|---|
| L1 | `log_level` de `app.yml` se aplica al logger `loom` | — | Sí, menor: el default del campo pasa a `None` |
| L2 | `TurnMetrics`: proyección tipada de un turno | — | No: solo agrega |
| L3 | `run_and_record` mide solo el turno | L2 | Sí: `.loom/stats` deja de guardar números acumulados |
| L4 | Puntos de debug del turno (`loom.turn`) | — | No |
| L5 | Hook builtin `metrics` con `sink` — en [`hook-de-metricas.md`](hook-de-metricas.md) | L2 | No |

Orden: L1, L2, L3, L4. L1 y L4 son independientes de L2. L5 va después de L2.

---

## L1. `log_level` se aplica al logger `loom`

### Cambio

- `AppConfig.log_level` pasa a `Literal[...] | None = None`. `None` = Loom no toca niveles.
- Precedencia, de mayor a menor:
  1. `LOOM_LOG_LEVEL` en el entorno.
  2. `log_level` de `app.yml`.
  3. Nada (queda lo que configuró el host, o `WARNING` heredado del root).
- Se aplica una vez por proceso, junto a `setup_telemetry` en [builder.py:409](../src/loom/core/builder.py#L409), con la misma guarda global.
- Solo `logging.getLogger("loom").setLevel(...)`. **No** agrega handlers ni toca otros loggers: Loom sigue siendo una librería y no elige el destino de los logs.
- **El host gana.** Si el logger `loom` ya tiene un nivel explícito (`level != NOTSET`) cuando se aplica, Loom no lo pisa y loguea en DEBUG que lo respetó. Así un host que configura logging al importar (como HostOrg con Powertools) no queda sobrescrito por el primer build.

### Tests

- `log_level: DEBUG` en `app.yml` → `logging.getLogger("loom").level == DEBUG` después del primer `build_agent`.
- `LOOM_LOG_LEVEL=WARNING` con `log_level: DEBUG` → `WARNING`.
- Logger `loom` con nivel puesto por el host → no cambia.
- Sin `log_level` ni variable → nivel `NOTSET` sin cambios.
- Dos builds → se aplica una sola vez.

### Docs

`docs/reference/app-yaml.md` (precedencia y regla del host) y `docs/guides/observability.md`.

---

## L2. `TurnMetrics`

### API

Módulo nuevo `loom.metrics`, exportado desde `loom`. Funciones puras sobre el resumen de Strands; no importan Powertools ni nada de AWS.

```python
class ModelCall(BaseModel, frozen=True):
    total_ms: int                # reloj de la traza stream_messages
    latency_ms: int | None       # message.metadata.metrics.latencyMs (Bedrock)
    first_token_ms: int | None   # message.metadata.metrics.timeToFirstByteMs
    # stop_reason: no se implementó — Strands no lo guarda en la traza stream_messages;
    # el final está en AgentResult (y en TurnContext de L5).

class ToolCall(BaseModel, frozen=True):
    tool_use_id: str
    name: str
    elapsed_ms: int
    status: Literal["success", "error"] | None

class Cycle(BaseModel, frozen=True):
    total_ms: int
    model: ModelCall | None
    tools: tuple[ToolCall, ...]

class TurnMetrics(BaseModel, frozen=True):
    duration_ms: int             # suma de ciclos
    model_ms: int                # suma de ModelCall.total_ms
    tools_ms: int                # suma de ToolCall.elapsed_ms
    other_ms: int                # max(0, duration - model - tools)
    cycles: tuple[Cycle, ...]
    usage: dict[str, int]        # agent_invocations[-1].usage (tokens, cache read/write)
    tool_errors: dict[str, int]

def turn_metrics(summary: dict, *, since_trace: int = 0) -> TurnMetrics: ...
def turn_metrics_of(agent, *, since_trace: int = 0) -> TurnMetrics: ...
```

- `since_trace`: índice de la primera traza del turno. `0` es correcto cuando el agente se construyó para este turno; quien reutiliza el agente pasa `len(agent.event_loop_metrics.traces)` tomado antes de invocar (L3 lo hace así).
- La semántica de cada número es la que hoy documenta HostOrg en `serverless-app/.docs/desglose-turno.md`: cada ciclo cierra antes de la llamada recursiva, así que sumar ciclos no cuenta dos veces; la traza `Recursive call` no entra; `latencyMs` y `timeToFirstByteMs` ya vienen en ms y `duration` de la traza en segundos. Ese documento se mueve a `docs/guides/observability.md` como referencia de L2.
- Tolerante a la forma: una traza sin los campos esperados se saltea (no lanza). Un resumen vacío da `TurnMetrics` en cero.
- **Nunca** guarda texto del modelo ni argumentos de tools: es seguro de loguear y de devolver.

### Dónde aparece

- `AgentResponseMetadata.turn: TurnMetrics | None` ([schemas/response.py:19](../src/loom/schemas/response.py#L19)), armado en `build_metadata` ([response.py:56](../src/loom/core/response.py#L56)). `raw_metrics` sigue igual.
- Weave lo usa desde `AgentReply` y `TurnEvent` (W10 de Weave).

### Tests

Fixtures con trazas reales de Strands 1.62 (copiar un `get_summary()` de `.loom/stats`):

- Un ciclo sin tools, dos ciclos con una tool, ciclo con dos tools en paralelo.
- `since_trace` corta los ciclos de turnos anteriores.
- Tool con error cuenta en `tool_errors` y su `ToolCall.status == "error"`.
- Traza malformada: no lanza.
- Los números de un caso real coinciden con el ejemplo de `desglose-turno.md`.

---

## L3. `run_and_record` mide solo el turno

### Cambio

En [response.py:167](../src/loom/core/response.py#L167), tomar `len(agent.event_loop_metrics.traces)` antes de `agent(...)` y pasarlo a `turn_metrics` vía `build_response`. `save_invocation` guarda `turn` (L2) además de `metrics`, y `stats_service` agrega sobre `turn` cuando existe (cae a `metrics` para registros viejos).

`metrics` (el `get_summary()` crudo) se sigue guardando, pero se documenta como acumulativo de la instancia.

### Tests

- Dos turnos sobre el mismo agente: el segundo registro tiene `turn.cycles` solo del segundo turno.
- `loom agent stats` con registros nuevos no suma dos veces.

---

## L4. Puntos de debug del turno

### Diseño

Un logger por área bajo `loom.turn`, más uno aparte para contenido:

| Logger | Qué |
|---|---|
| `loom.turn` | metadatos del turno: nunca texto del usuario, del modelo ni de las tools |
| `loom.turn.content` | contenido: input del turno, argumentos de tools, primeros N caracteres del resultado |

`loom.turn.content` existe para que el host lo prenda a propósito. En producción el contenido es texto de usuarios y respuestas de APIs internas. Al ser hijo de `loom.turn`, hereda su nivel salvo que el host le ponga uno; L1 lo deja en `WARNING` explícito al aplicar el nivel para que `log_level: DEBUG` no lo arrastre.

Un hook interno (`TurnDebugHook`) que el builder registra en cada agente. Los callbacks de DEBUG se registran solo si `loom.turn` está habilitado para DEBUG en el momento del build (costo cero si no). Los de WARNING (tool fallida, reintento de modelo) se registran siempre. No se declara en YAML: así no se pierde cuando un agente declara sus propios `hooks` (que reemplazan a `defaults.hooks`).

### Puntos

Todos con `agent` y `session_id`.

| Momento | Evento Strands | Nivel | Campos |
|---|---|---|---|
| Agente listo | (builder, [builder.py:331](../src/loom/core/builder.py#L331)) | DEBUG | `model_id`, tools (nombres), conversation manager y su ventana, session manager y su ubicación (bucket/prefix o dir), mensajes restaurados de la sesión, ms de build |
| Inicio del turno | `BeforeInvocationEvent` | DEBUG | mensajes en contexto, tokens estimados del system prompt |
| Antes del modelo | `BeforeModelCallEvent` | DEBUG | ciclo, mensajes enviados |
| Después del modelo | `AfterModelCallEvent` | DEBUG | ciclo, `stop_reason`, tokens in/out/cache, `latencyMs`, `timeToFirstByteMs`, ms de reloj |
| Reintento de modelo | (retry strategy / router de modelos) | **WARNING** | intento, motivo (clase de excepción), espera, modelo |
| Antes de tool | `BeforeToolCallEvent` | DEBUG | tool, `toolUseId`, nombres de parámetros |
| Después de tool | `AfterToolCallEvent` | DEBUG (WARNING si falló) | tool, `toolUseId`, status, ms, tamaño del resultado |
| Recorte de conversación | después de `reduce_context` / `apply_management` | DEBUG | mensajes antes/después, `removed_message_count`, resultados truncados |
| Fin del turno | `AfterInvocationEvent` | DEBUG | `TurnMetrics` (L2) resumido: ciclos, model/tools/other ms, `stop_reason` final |
| Contenido | Before/AfterToolCall, BeforeInvocation | DEBUG en `loom.turn.content` | input del turno, argumentos, resultado recortado a 500 caracteres |

### A verificar al implementar

- Qué loguea hoy Strands de los reintentos (`strands.event_loop`) y si alcanza con documentar que hay que habilitar `strands` en WARNING, o si Loom tiene que loguear cada intento desde el router de modelos (`_loom_routing_trace`, [builder.py:329](../src/loom/core/builder.py#L329)).
- Si el conversation manager expone algo observable del recorte sin envolverlo.
- Relación con los hooks `logging` y `tool_tracker`: hoy `tool_tracker` loguea el input completo en DEBUG ([tool_tracker.py:46](../src/loom/hooks/tool_tracker.py#L46)) en `loom.hooks.tool_tracker`. Propuesta: deprecarlos a favor de `loom.turn`, o que pasen a usar `loom.turn.content` para el contenido.

### Tests

- Con `loom.turn` en DEBUG, un turno con una tool emite los eventos de la tabla en orden, sin contenido.
- Con `loom.turn` en INFO, el hook no se registra.
- `loom.turn.content` en DEBUG agrega el contenido; con `loom.turn` en DEBUG solo, no.
- Una tool que falla emite el WARNING con `loom.turn` en INFO o WARNING. Por eso la parte de "tool fallida" no puede depender del hook de DEBUG: se registra siempre, y el resto del hook solo con DEBUG.

### Docs

`docs/guides/observability.md`: tabla de loggers, qué prender en dev y qué en producción.

---

## 3. Fuera de alcance

- Publicar métricas con un SDK (Powertools, `PutMetricData`, OTel metrics): es de Weave (W8) o del producto. L5 ([`hook-de-metricas.md`](hook-de-metricas.md)) ajusta esto: Loom entrega `TurnMetrics` a un `sink` y trae dos sin dependencias (logger y EMF a stdout); el resto sigue siendo del producto.
- Trazas OpenTelemetry: ya están en el bloque `telemetry`.
- Correlation id / request id: lo pone el host (Powertools) en el formatter; los loggers de Loom lo heredan.
