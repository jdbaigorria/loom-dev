# Especificación: hook builtin `metrics`

| | |
|---|---|
| **Estado** | Implementada (rama `feat/turn-metrics`) |
| **Fecha** | 2026-11-02 |
| **Origen** | HostOrg (`host-agentics`): `serverless-app/.docs/spec-metricas-hook.md` publica métricas desde un hook propio; nada de ese hook es de HostOrg salvo el destino |
| **Depende de** | L2 (`TurnMetrics`) de [`observabilidad-del-turno.md`](observabilidad-del-turno.md) |
| **Relacionado** | Weave [`weave-metricas-de-turno.md`](../../weave-dev/specs/weave-metricas-de-turno.md) (W5–W8): reparto de métricas en "Convivencia con Weave W8" |

---

## 1. Motivación

L2 deja a Loom calculando `TurnMetrics`, pero alguien tiene que llamarlo en cada turno y mandar el resultado a algún lado. Hoy cada producto lo resuelve a mano: HostOrg lo hace en el `render` del contrato HTTP, y su spec propone moverlo a un hook propio declarado en `defaults.hooks`. Ese hook tiene tres partes y solo una es de HostOrg:

1. **Marcar el turno** en `BeforeInvocationEvent` (`len(traces)`), porque el resumen de Strands es acumulativo cuando el agente se reutiliza (§1.1 de `observabilidad-del-turno.md`).
2. **Armar `TurnMetrics`** en `AfterInvocationEvent`, que Strands 1.62 dispara en un `finally`: también corre cuando la ejecución falla, con `result=None` y las trazas parciales.
3. **Publicar** con Powertools y los nombres de métricas de HostOrg.

Las partes 1 y 2 son iguales para cualquier agente. El builtin las resuelve, y la 3 queda parametrizada como un `sink`.

### 1.1 Qué cambia respecto de L1–L4

`observabilidad-del-turno.md` deja afuera "publicar métricas: es de Weave (W8) o del producto. Loom solo calcula". Esta spec lo ajusta así:

- Loom sigue sin depender de AWS ni de Powertools.
- El builtin entrega `TurnMetrics` a un `sink`. Los dos sinks que trae Loom escriben a un logger o a stdout, con la biblioteca estándar.
- Publicar con un SDK (Powertools, `PutMetricData`, OTel metrics) sigue siendo del producto, con un sink propio.

---

## 2. Spec

| # | Spec | Depende de | Rompe compatibilidad |
|---|---|---|---|
| L5 | Hook builtin `metrics` con `sink` | L2 | No: solo agrega |

---

## L5. Hook builtin `metrics`

### YAML

```yaml
# app.yml — para todos los agentes
defaults:
  hooks:
    - metrics                              # sink: log (default)

# o con EMF
defaults:
  hooks:
    - metrics:
        sink: emf
        namespace: MiProducto/Agentes
        service: mi-producto               # opcional: suma la dimensión service
        include: [invocation, breakdown, tools]
        enabled: ${oc.env:LOOM_METRICS_ENABLED,true}

# o con un destino del producto
defaults:
  hooks:
    - metrics:
        sink: mi_producto.metricas:publicar
```

`enabled` no es magia del hook: es un parámetro `bool` más, y la interpolación `${oc.env:...}` ya la resuelve OmegaConf al cargar `app.yml`. Así un REPL o un test lo apaga sin tocar el YAML.

### Parámetros

| Parámetro | Tipo | Default | Qué hace |
|---|---|---|---|
| `sink` | `"log"` \| `"emf"` \| `"modulo:funcion"` | `"log"` | Destino de cada `TurnMetrics` |
| `include` | lista de `invocation`, `breakdown`, `tools` | las tres | Solo `emf`: qué grupos se emiten (ver tabla); con otro sink, `HookLoadError` |
| `namespace` | `str` | — | Obligatorio con `sink: emf`; con otro sink, `HookLoadError` si se pasa |
| `service` | `str \| None` | `None` | Solo `emf`: dimensión `service` y propiedad |
| `enabled` | `bool` o string (`true`/`false`/`1`/`0`/`yes`/`no`/`on`/`off`) | `True` | `False` registra el hook sin callbacks (costo cero). Acepta strings porque `${oc.env:...}` devuelve strings |

Un parámetro desconocido o un `sink` que no importa da `HookLoadError` al construir, como cualquier hook hoy.

### Comportamiento

```python
class MetricsHook(HookProvider):
    def register_hooks(self, registry, **kwargs) -> None:
        registry.add_callback(BeforeInvocationEvent, self._mark)
        registry.add_callback(AfterInvocationEvent, self._emit)
```

- **`_mark`** guarda `len(event.agent.event_loop_metrics.traces)` en la instancia.
- **`_emit`** arma `turn_metrics_of(event.agent, since_trace=marca)` (L2) y un `TurnContext`, y llama al sink.
- **Sin marca** (no corrió `_mark`): `since_trace=0`.
- **Nunca rompe el turno.** Strands propaga las excepciones de los callbacks de `AfterInvocationEvent`. Todo `_emit` va en `try/except Exception` y loguea un `WARNING` con traceback en `loom.hooks.metrics`. Un sink que lanza recibe el mismo trato.
- **Una instancia por build.** `get_hooks` instancia el hook en cada `build_agent`, así que la marca no se comparte entre agentes. Con un agente reutilizado, la marca se pisa en cada `BeforeInvocationEvent`.

### `TurnContext`

Lo que el sink necesita además de los números, sin contenido:

```python
class TurnContext(BaseModel, frozen=True):
    agent: str                    # event.agent.name: el nombre del YAML (builder.py pasa name=name)
    session_id: str | None
    user_id: str | None
    outcome: Literal["ok", "error"]
    stop_reason: str | None       # result.stop_reason si hay result
```

- `outcome`: `"ok"` si `event.result` no es `None`, si no `"error"`.
- `session_id` / `user_id`: el hook no ve la `LoomSession`. El builder se la pasa después de `get_hooks` con un protocolo chico:

  ```python
  class SessionAwareHook(Protocol):
      def loom_bind(self, *, agent: str, session: LoomSession) -> None: ...
  ```

  El builder llama `loom_bind` en cada hook cargado que lo implemente, sea builtin o del usuario. Así un hook propio también puede recibir la identidad sin leer `invocation_state`. Si no se llamó (hook construido a mano fuera del builder), quedan en `None`.
- **No** incluye `invocation_state`: puede traer secretos (`model_params`, credenciales por cliente).

### Sinks

**`log`.** Una línea `INFO` por turno en el logger `loom.metrics`: `"turn agent=%s outcome=%s duration_ms=%d model_ms=%d tools_ms=%d cycles=%d tokens=%d"`, con `extra={"turn": metrics.model_dump(), "context": context.model_dump()}` para formatters JSON (Powertools lo vuelca entero). Es el default porque funciona en cualquier host y no escribe nada que el host no haya pedido: si nadie configuró `loom.metrics` en `INFO`, no sale.

**`emf`.** Una línea JSON por grupo escrita con `print(json.dumps(doc), flush=True)` a `sys.stdout`, resuelto al momento de escribir. Va directo a stdout y no por `logging`, por lo mismo que W8: EMF necesita la línea entera.

| Grupo | Dimensiones | Métrica | Unidad | Valor |
|---|---|---|---|---|
| `invocation` | `agent` (+`service`) | `Invocations` | Count | 1 |
| | | `InvocationErrors` | Count | 1 si `error`, si no 0 |
| | | `InvocationDuration` | Milliseconds | `duration_ms` |
| | | `InputTokens`, `OutputTokens`, `TotalTokens` | Count | de `usage`, solo con `ok` |
| `breakdown` | `agent` (+`service`) | `ModelDuration` | Milliseconds | `model_ms` |
| | | `ToolsDuration` | Milliseconds | `tools_ms` |
| | | `OtherDuration` | Milliseconds | `other_ms` |
| | | `Cycles` | Count | `len(cycles)` |
| `tools` | `agent`, `tool` (+`service`) | `ToolDuration` | Milliseconds | `elapsed_ms` de cada `ToolCall` |
| | | `ToolInvocations` | Count | 1 por llamada |
| | | `ToolErrors` | Count | 1 si `status == "error"`, si no 0 |

- `invocation` y `breakdown` van en una sola línea (mismas dimensiones). `tools` emite una línea por llamada, porque cambia la dimensión `tool`.
- Propiedades (no dimensiones) en cada línea: `session_id`, `user_id`, `outcome`, `stop_reason`. `session_id` y `user_id` nunca son dimensión: cada combinación es una métrica facturada aparte.
- `InvocationErrors` se emite también en 0, para calcular la tasa como `InvocationErrors / Invocations` sin huecos (mismo criterio que `TurnErrors` en W8).
- Los nombres no repiten los de W8 (`Turns`, `TurnErrors`, `TurnDuration`, `ToolCalls`) a propósito: miden otra ventana (ver "Convivencia con Weave W8").

**`modulo:funcion`.** Se resuelve con `import_attr` al construir el hook. Firma: `(metrics: TurnMetrics, context: TurnContext) -> None`. `include` no aplica: el sink recibe el `TurnMetrics` entero y decide.

### Convivencia con Weave W8

W8 (`EmfTurnObserver`) mide el **turno de Weave**: build incluido, una vez por turno aunque sea un workflow, y también cuando el build falla. Este hook mide la **invocación del agente**: lo que pasa adentro de `agent(...)`, una vez por agente (en un workflow, una por nodo), y no existe si el build falló.

Reparto recomendado para un producto que usa los dos:

| Qué | Quién |
|---|---|
| Turnos, errores (build incluido), duración de pared, tokens del turno | Weave W8 |
| Desglose modelo / tools / resto, ciclos | Loom L5, `include: [breakdown]` |
| Duración, llamadas y errores por tool | Loom L5, `include: [tools]` |

Con W8 configurado, `include` no debería llevar `invocation`: los tokens se contarían dos veces. Sin Weave (REPL, otro backend, un script), `invocation` es lo que da conteos y tokens. La guía lo dice con estas dos configuraciones de ejemplo.

### Limitaciones (documentar)

- **El build fallido no se ve.** Si `build_agent` lanza, el agente no existe y el hook no corre. Eso lo cubre W8 o el host.
- **Se pierde si un agente declara `hooks` propios.** `defaults` se mezcla con `OmegaConf.merge`, y las listas se reemplazan, no se suman ([file_source.py:91-101](../src/loom/adapters/config/file_source.py#L91-L101)). Un agente con `hooks: [rate_limit]` pierde el `metrics` de `defaults` sin aviso. Esta spec no cambia la regla de merge; lo documenta en `hooks.md` y en el ejemplo pone `metrics` repetido en el agente que suma hooks.
- **Workflow:** una emisión por nodo, con `agent` = nombre del nodo.

### Resuelto al implementar

- **Bidi:** `metrics` en un agente `kind: bidi` da `AgentConfigError` al construir.
- **`SessionAwareHook`** vive en `loom.core.loaders.hook` junto con `bind_hooks`, que el builder llama después de `get_hooks`. Es un `Protocol` `runtime_checkable`: cualquier hook con `loom_bind` lo recibe.
- **Cancelación por hook:** no se distingue. Queda documentada como limitación (se reporta como `error`).
- **L4:** no está implementado; cuando exista, ver si comparte el cálculo con este hook.
- **`include` y `enabled`:** ver la tabla de parámetros (solo `emf`; strings aceptados).

### A verificar al implementar (texto original)

- **Bidi:** `BidiAgent` recibe `hooks` ([builder.py:191-206](../src/loom/core/builder.py#L191-L206)) pero sus eventos no son `Before/AfterInvocationEvent`. Propuesta: `metrics` en un agente `kind: bidi` da `AgentConfigError` al construir, como `trace_attributes`.
- **Cancelación por hook:** `BeforeInvocationEvent.cancel` termina con `AfterInvocationEvent` sin `result` (`strands/agent/agent.py:1654` en 1.62), que este hook contaría como `error`. Confirmar si se puede distinguir (por ejemplo, `cancel` en el evento previo) y si vale un `outcome="cancelled"`.
- **Orden de callbacks:** `AfterInvocationEvent` usa orden inverso. Si L4 (`TurnDebugHook`) también arma `TurnMetrics`, ver si conviene que lo calcule uno solo y lo deje en el agente para el otro.

### Tests

Unitarios, con eventos armados a mano (sin modelo):

- **Turno ok:** el sink recibe `TurnMetrics` y `TurnContext(outcome="ok", agent=<name>)`.
- **Turno fallido:** `After` con `result=None` y trazas parciales: `outcome="error"`, las tools que corrieron están en `metrics.cycles`.
- **Agente reutilizado:** dos turnos, y el segundo `TurnMetrics` tiene solo los ciclos del segundo (vía la marca).
- **Sink que lanza:** no propaga y loguea un `WARNING`.
- **`enabled: false`:** no se registran callbacks.
- **`emf`:** JSON válido, con `_aws.Timestamp` en ms, cada métrica declarada con su valor en la raíz y `session_id` fuera de `Dimensions`. `include: [tools]` no emite `Invocations`. Una línea por tool call. `InvocationErrors=0` en `ok`. Sin tokens en `error`.
- **`log`:** con `loom.metrics` en `INFO`, una línea con `extra["turn"]`. En `WARNING`, nada.
- **`modulo:funcion`** inexistente: `HookLoadError`. `namespace` con `sink: log`: `HookLoadError`.
- **`loom_bind`:** `build_agent` con una sesión deja `session_id`/`user_id` en el `TurnContext`. Un hook del usuario con `loom_bind` también lo recibe.

Integración (build real, modelo falso): `defaults.hooks: [metrics]` en `app.yml` llega al agente. Un agente con `hooks` propios no lo tiene (documenta la regla del merge).

### Docs

- `docs/guides/hooks.md`: `metrics` en la tabla de builtins, `loom_bind` para hooks propios y la regla de que `hooks` del agente reemplaza `defaults.hooks`.
- `docs/guides/observability.md`: sección "Métricas" con los tres sinks, la tabla de EMF y las dos configuraciones (con Weave W8 y sin Weave).
- Docstring de `loom/hooks/__init__.py` y `REGISTRY` en `loom/core/loaders/hook.py`.

---

## 3. Fuera de alcance

- Sinks de Powertools, `PutMetricData` u OTel metrics dentro de Loom: el producto los escribe como `modulo:funcion`.
- Cambiar la regla de merge de `defaults.hooks` (sumar en vez de reemplazar): rompe compatibilidad, spec aparte si hace falta.
- Métricas por llamada al modelo (`ModelCallDuration`, `ModelFirstToken` por fase): `TurnMetrics.cycles` ya las trae; se suma un grupo `model_calls` cuando un producto lo pida.
