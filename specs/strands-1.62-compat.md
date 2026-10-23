# Especificación: compatibilidad con Strands 1.62 (mcp 2.x, strands-agents-evals 1.x)

| | |
|---|---|
| **Estado** | Propuesta — pendiente de implementación |
| **Fecha** | 2026-10-23 |
| **Rama** | `fix/strands-1.62-compat` (desde `dev` @ `150f953`) |
| **Alcance** | Capa anticorrupción (`loom.adapters.strands`), loaders de MCP / bidi / evals / workflows, dependencias, CI |

---

## 1. Resumen

El SDK de Strands para Python ahora se desarrolla dentro del monorepo
[`strands-agents/harness-sdk`](https://github.com/strands-agents/harness-sdk/tree/main/strands-py)
(carpeta `strands-py`), pero **sigue publicándose en PyPI como `strands-agents`** y sigue en la
línea 1.x. La última versión es **1.62.0**. No existe una 2.0.

Loom declara `strands-agents>=1.34,<2.0`, así que **toda instalación nueva hoy recibe Strands
1.62.0**, y con ella `mcp` 2.1.1 (Strands 1.62 permite `mcp<2.2`). El `uv.lock` sigue en 1.34.1, por
lo que el entorno de desarrollo no refleja lo que reciben los usuarios.

Resultado de la validación:

- La suite da **el mismo resultado** con 1.34.1 y con 1.62.0 (649 tests pasan). La capa
  anticorrupción resuelve todos los símbolos.
- Aun así hay **3 roturas reales en runtime que la suite no detecta**, porque los tests mockean
  justo los puntos de integración afectados (ver §5, F6).
- Además hay deprecaciones con fecha de retiro ya vencida, un bug conocido en los evaluators y un
  problema de Windows que impide clonar el repo e instalar el paquete.

| ID | Hallazgo | Severidad | Afecta desde |
|---|---|---|---|
| F0 | Ruta con `\|` en `templates/init/` rompe el checkout y la instalación en Windows | **Alta** (Windows) | — (no depende de Strands) |
| F1 | MCP `transport: http` falla con `LoomStrandsCompatError` | **Crítica** | strands 1.55 + mcp ≥ 2.0 |
| F2 | Agente `kind: bidi` + `tool_executor` lanza `TypeError` | **Alta** | strands 1.57.2 |
| F3 | Ruta `strands.experimental.bidi` deprecada (retiro anunciado para v1.60.0) | Media | strands 1.57.2 |
| F4 | Evals ≥ 0.3: forma del reporte, nombres de evaluators e `include_inputs` | Media (latente por el pin `<0.2`) | evals 0.3.0 |
| F5 | Graphs sin límites de ejecución: Strands avisa "execution is unbounded" | Baja | strands 1.60.0 |
| F6 | Puntos ciegos en tests/CI: la suite pasa en verde con F1, F2 y F4 | **Alta** (proceso) | — |
| F7 | Menores: fallback muerto, lock desactualizado, documentación | Baja | — |

---

## 2. Entornos evaluados y método

| Entorno | strands-agents | mcp | strands-agents-evals | Suite |
|---|---|---|---|---|
| A — lock actual | 1.34.1 | 1.26.0 | 0.1.13 | 649 ✅ / 9 ❌ / 4 xfail |
| B — Strands actual | 1.62.0 | 2.1.1 | 0.1.13 | 649 ✅ / 9 ❌ / 4 xfail |
| C — todo actual | 1.62.0 | 2.1.1 | 1.7.0 | 649 ✅ / 9 ❌ / 4 xfail |

Python 3.14 (el `.python-version` del repo), Windows 11. Los **9 fallos son idénticos en los tres
entornos** y vienen del entorno Windows, no de Strands (ver F0): 7 de integración porque la carpeta
de plantilla no puede existir en NTFS, y 2 de `test_dev_reload` que asumen el separador `/`. Los 4
xfail son el bug conocido `_INCLUDE_INPUTS_BUG` (ver F4.3).

Método:

1. Suite completa en los tres entornos, con `-W default` para ver los warnings nuevos.
2. Diff de firmas (`inspect.signature`) de todo constructor o método de Strands/evals que Loom
   llama, comparando los kwargs que Loom realmente pasa.
3. Escaneo de los wheels publicados en PyPI (strands 1.34.0 → 1.62.0, evals 0.1.13 → 1.7.0) para
   fechar cada cambio (§3).
4. Reproducción end-to-end **con el código real de Loom, sin mocks ni LLM** (script en el Anexo A).

Consultas de DeepWiki sobre `harness-sdk` sirvieron de contexto (nombre del paquete, capa de
compatibilidad `strands/tools/mcp/_compat.py`, guía `strands-py/docs/MCP_VERSIONS.md`). Todas las
afirmaciones de esta especificación se verificaron contra el código instalado o los wheels.

---

## 3. Cronología upstream relevante

| Versión | Cambio | Impacto en Loom |
|---|---|---|
| strands **1.53.0** | `MCPClient(url=, headers=, auth=…)` construye su propio transporte streamable-HTTP | Habilita el arreglo de F1 |
| strands **1.55.0** | Requisito `mcp<2.0.0` → `mcp<2.2` (entra mcp 2.x) | Dispara F1 |
| strands **1.57.2** (patch) | Nuevo `strands.bidi`. `strands.experimental.bidi` pasa a alias deprecado. `BidiAgent.__init__` pierde `tool_executor`, `load_tools_from_directory` y `**kwargs`, y suma `storage` | F2, F3 |
| strands **1.60.0** | `GraphBuilder.build()` emite `UserWarning` si no hay `max_node_executions` ni `execution_timeout` | F5 |
| evals **0.3.0** | `run_evaluations` devuelve **un** `EvaluationReport` combinado. Se elimina `EvaluationReport.evaluator_name` (ahora cada fila lleva `cases[i]["evaluator"]`). Nombres de evaluators únicos obligatorios. Requiere strands ≥ 1.42 | F4 |
| evals **1.4.0** | Requiere strands ≥ 1.45 | Ajuste de rangos |
| evals **1.5.0** | `run_evaluations -> ReportT` (`report_cls` configurable; por defecto `EvaluationReport`) | F4 |
| evals **1.6.0** | Requiere `rich>=15,<16` | Compatible con `rich>=14.3.3` de Loom; la suite pasa con rich 15.0.0 |

Consecuencia clave para F1: hasta strands 1.54, Strands fija `mcp<2`, así que el transporte
`streamablehttp_client` siempre existe. Desde 1.53 existe `MCPClient(url=)`. **Con detección de
capacidades, cada versión del rango `>=1.34` tiene un camino que funciona**; no hace falta subir el
piso de `strands-agents`.

---

## 4. Lo que no requiere cambios (verificado en 1.62.0)

- **Símbolos de la ACL:** todas las rutas de `loom/adapters/strands/__init__.py` y `evals.py`
  resuelven (salvo las de F3/F7, que se describen abajo).
- **Constructores con los kwargs que Loom pasa:** `Agent`, `ModelRetryStrategy`, `BedrockModel`,
  `SlidingWindowConversationManager`, `SummarizingConversationManager`, `FileSessionManager`,
  `S3SessionManager`, `Swarm`, `GraphBuilder.add_node/add_edge/set_entry_point`,
  `StrandsTelemetry.setup_*`. Los cambios son solo aditivos.
- **Eventos de hooks:** `BeforeToolCallEvent.cancel_tool` sigue siendo escribible. `tool_use`,
  `exception` y `AfterInvocationEvent.result` siguen ahí. Hay campos nuevos (`cancel`, `duration`)
  que no afectan a Loom.
- **`AgentResult`:** `message`, `stop_reason` y `metrics.get_summary()` (`accumulated_usage`,
  `total_duration`, `tool_usage`) están cubiertos por `tests/unit/test_strands_contract.py`, que pasa.
- **Transportes MCP `stdio` y `sse`:** `mcp.client.stdio.stdio_client`, `mcp.StdioServerParameters`
  y `mcp.client.sse.sse_client(url, headers)` mantienen la firma en mcp 2.1.1.
- **Internals privados:** Loom no usa ninguno de Strands. El único acceso privado es a su propio
  `MockModel._responses`.
- **A2A:** `has_a2a()` da `False` en ambas versiones porque falta el extra `a2a`. Es el
  comportamiento esperado.

---

## 5. Hallazgos y arreglos

### F0 — Ruta inválida en Windows en la plantilla de `loom init` · **Alta (Windows)**

**Síntoma**

- `git clone` en Windows termina sin hacer checkout: `error: invalid path
  'src/loom/templates/init/{{ app.workspace_name | default('warp') | lower | replace(' ', '_') }}/…'`.
  Queda sin `.git/index` y los 217 archivos aparecen como borrados en el stage.
- Instalar un wheel que contenga esa ruta falla en Windows. Se verificó con `uv pip install` y un
  wheel sintético con la misma forma de ruta: `failed to create directory … {{ a | lower }}: The
  filename, directory name, or volume label syntax is incorrect. (os error 123)`. El paquete aún no
  está en PyPI, así que no hay usuarios afectados, pero bloquearía toda instalación en Windows.

**Causa:** `|` es un carácter reservado en NTFS. El resto de nombres con plantilla
(`{{folder_name}}.yml.j2`, `{% if prompt == 'prompts' %}prompts{% endif %}`) son válidos en Windows.

**Arreglo**

1. Renombrar la carpeta a `src/loom/templates/init/{{ workspace_dir }}/`. `utils/render.py:80` ya
   renderiza las rutas relativas con Jinja, así que no hace falta otro mecanismo.
2. Derivar `workspace_dir` **en un solo lugar** y añadirlo al contexto de render. Hoy el contexto
   se arma en tres sitios: `cli/commands/init.py:28` (`init_ctx.to_template_context()`),
   `cli/commands/init.py:31` (`{"app": app_config.model_dump(...)}`) y
   `services/project_service.py:190`. Propuesta: un helper (p. ej. junto a
   `core/paths/naming.py`) que replique exactamente el filtro actual:
   ```python
   def workspace_dir_name(workspace_name: str | None) -> str:
       return (workspace_name or "warp").lower().replace(" ", "_")
   ```
   Hay que inyectarlo antes de renderizar, de modo que ningún llamador pueda olvidarlo.
3. Corregir los dos tests que asumen `/` (`tests/unit/test_dev_reload.py:15` y `:43`): usar
   `Path(p).name` y `Path(p).as_posix().endswith("tools/t.py")`. `_fingerprint` en
   `cli/commands/dev.py:30` es correcto; el problema está solo en los tests.
4. Añadir un guard en CI que falle si alguna ruta versionada contiene `<>:"|?*` (por ejemplo
   `git ls-files | grep -n '[<>:"|?*]'`).

**Tests:** los 7 de `tests/integration/test_workflow.py` y los 2 de `test_dev_reload` pasan en
Windows; `loom init` genera el mismo árbol que hoy (mismo nombre de workspace).

---

### F1 — MCP con `transport: http` roto con mcp 2.x · **Crítica**

**Afecta:** strands ≥ 1.55 cuando se resuelve `mcp` ≥ 2.0. Es la resolución por defecto hoy.

**Síntoma** (reproducido con `get_mcp_clients`, sin mocks):
```
LoomStrandsCompatError: Loom could not resolve a required Strands symbol. None of these import paths worked:
  - mcp.client.streamable_http.streamablehttp_client
Last error: ModuleNotFoundError("No module named 'mcp.client.streamable_http.streamablehttp_client'; …")
```
Cualquier agente con un servidor MCP `transport: http` falla al construirse.

**Causa:** `core/loaders/mcp.py:26-43` (`_build_transport`) importa el transporte de `mcp` en forma
directa. mcp 2.0 lo renombró a `streamable_http_client`, que además **ya no acepta `headers=`**
(ahora recibe `http_client: httpx2.AsyncClient`). Este acoplamiento a `mcp` vive fuera de la ACL en
la práctica: la regla ruff `banned-api` cubre `strands`, pero no `mcp` ni las rutas en strings.

**Arreglo**

1. Nueva capacidad en `adapters/strands/capabilities.py`:
   ```python
   @cache
   def mcp_client_accepts_url() -> bool:
       """True if ``MCPClient`` builds its own streamable-HTTP transport from ``url=`` (Strands >= 1.53)."""
       client = resolve("strands.tools.mcp.MCPClient", "strands.tools.mcp.mcp_client.MCPClient", optional=True)
       return client is not None and "url" in inspect.signature(client.__init__).parameters
   ```
   Hay que sumarla también a `snapshot()` para que aparezca en `loom doctor`.
2. Mover las rutas de `mcp.*` a la ACL, en un módulo nuevo `adapters/strands/mcp.py` con
   `stdio_transport(command, args, env)`, `sse_transport(url, headers)` y
   `legacy_streamable_http_transport(url, headers)`. Así, todos los paths del vendor quedan en
   `adapters/strands/`, como promete el diseño.
3. En `core/loaders/mcp.py`, construir el cliente según la capacidad:
   ```python
   def _build_client(server: MCPServerConfig):
       if isinstance(server, StdioMCPServer):
           transport = sx_mcp.stdio_transport(server.command, server.args, server.env)
           return sx.MCPClient(transport, prefix=server.name)
       if server.transport == "http" and capabilities.mcp_client_accepts_url():
           # Strands owns the mcp 1.x/2.x differences (strands/tools/mcp/_compat.py).
           return sx.MCPClient(url=server.url, headers=server.headers, prefix=server.name)
       transport = (
           sx_mcp.sse_transport(server.url, server.headers)
           if server.transport == "sse"
           else sx_mcp.legacy_streamable_http_transport(server.url, server.headers)  # Strands < 1.53 ⇒ mcp < 2
       )
       return sx.MCPClient(transport, prefix=server.name)
   ```
   Con `url=`, `MCPClient` valida el esquema (`http://` / `https://`) y lanza `ValueError` al
   construirse. Hay que envolverlo en `AgentConfigError` con un `tip` claro.
4. Ampliar `banned-api` en `pyproject.toml` con `"mcp".msg = "Import mcp only via
   loom.adapters.strands"`. Cubre importaciones directas a futuro, aunque no las rutas en strings.
5. Parche rápido, **solo si hubiera que liberar antes del arreglo:** añadir `mcp<2` a las
   dependencias. No es la solución recomendada: congela a los usuarios en mcp 1.x.

**Tests** (sin mockear `_build_transport` ni `MCPClient`; construir un `MCPClient` no conecta):

- `http` → `get_mcp_clients` devuelve un `MCPClient` con `prefix` correcto, en los dos extremos
  del rango (strands 1.34 / mcp 1.x y strands 1.62 / mcp 2.x).
- `sse` y `stdio` → ídem.
- URL con esquema inválido → `AgentConfigError`.

**Aceptación:** el Anexo A imprime `[MCP http] OK` en los entornos A, B y C.

---

### F2 — `kind: bidi` + `tool_executor` lanza `TypeError` · **Alta**

**Afecta:** strands ≥ 1.57.2.

**Síntoma:** `TypeError: BidiAgent.__init__() got an unexpected keyword argument 'tool_executor'`.

**Causa:** `core/builder.py:159-170` incluye `tool_executor` en `shared_params`, y
`_build_bidi` (`core/builder.py:201`) lo pasa a `sx.BidiAgent(...)` en la línea 218. En 1.57.2
`BidiAgent` eliminó `tool_executor` **y también `**kwargs`**, así que ya no lo absorbe en silencio.

**Arreglo**

1. Capacidad `bidi_accepts_tool_executor()` en `capabilities.py`: inspeccionar
   `BidiAgent.__init__` y buscar `tool_executor`.
2. En `_build_bidi`, antes de construir:
   ```python
   if "tool_executor" in clean_params and not capabilities.bidi_accepts_tool_executor():
       raise AgentConfigError(
           "'tool_executor' is not supported for bidi agents by the installed Strands version.",
           tip="Remove 'tool_executor' from the agent YAML (Strands >= 1.57.2 dropped it from BidiAgent).",
       )
   ```
   **No** descartarlo en silencio: Loom valida temprano y no ignora configuración.
3. Documentar la restricción en `docs/reference/agent-yaml.md` (sección `tool_executor`).

**Tests:** con strands ≥ 1.57.2, `_build_bidi` con `tool_executor` lanza `AgentConfigError` sin
llegar a construir el modelo. Con una versión anterior, el kwarg se pasa (hacer `skip` según la
capacidad).

---

### F3 — `strands.experimental.bidi` deprecado · **Media**

**Afecta:** strands ≥ 1.57.2. En cada `import loom` aparece:
`DeprecationWarning: strands.experimental.bidi is deprecated and will be removed in v1.60.0. Import
from strands.bidi instead.` Ya estamos en 1.62 y el alias sigue, pero **puede desaparecer en
cualquier release**. Cuando pase, `sx.BidiAgent` quedará en `None` y el error
("does not provide the experimental BidiAgent") dará una pista equivocada.

**Causa:** el orden de candidatos en `adapters/strands/__init__.py:113` y en
`capabilities.has_bidi()` (`capabilities.py:97`) pone primero la ruta experimental.

**Arreglo**

```python
BidiAgent = resolve(
    "strands.bidi.BidiAgent",
    "strands.bidi.agent.BidiAgent",
    "strands.experimental.bidi.BidiAgent",          # Strands < 1.57.2
    "strands.experimental.bidi.agent.BidiAgent",
    optional=True,
)
```

- Mismo orden en `has_bidi()`.
- Actualizar el `tip` de `core/builder.py:212` para mencionar `strands.bidi`.

Verificado: `strands.bidi.BidiAgent is strands.experimental.bidi.BidiAgent` en 1.62, y
`import strands.bidi` no emite warnings.

**Tests:** contrato que importa `loom.adapters.strands` con `warnings.simplefilter("error",
DeprecationWarning)` en un subproceso y no falla. Si existe `strands.bidi`, además
`sx.BidiAgent.__module__` no debe empezar por `strands.experimental`.

---

### F4 — strands-agents-evals ≥ 0.3 · **Media (latente)**

Hoy el pin `strands-agents-evals>=0.1.13,<0.2` (`pyproject.toml:27`) protege a Loom, y evals 0.1.x
funciona con strands 1.62 (entorno B). Pero evals ya va por la 1.7.0, y para subir el pin hay que
resolver estos tres puntos.

#### F4.1 Forma del reporte

**Síntoma** (entorno C, `Experiment.run_evaluations` real + el manejo de Loom):
`TypeError: object of type 'EvaluationReport' has no len()`.

**Causa:** desde 0.3.0, `run_evaluations` devuelve un único reporte combinado, y la columna
`evaluator` va en cada fila de `cases`. Loom asume una lista con `evaluator_name` en:

- `loom_evals.py:98` (`len(reports)`), `:122` (`report.evaluator_name`), `:135` (`report.to_dict()`
  por evaluator)
- `loom_evals.py:304`, `:324-325`, `:382` (registros persistidos que esperan `evaluator_name`)
- `cli/renders/evals_renderer.py:76` y `:97`

**Arreglo**

1. Normalizar en la ACL de evals (`adapters/strands/evals.py`), ya que es adaptación a la forma del
   vendor:
   ```python
   def split_reports(result, names: list[str]) -> list[tuple[str, Any]]:
       """Normalize ``run_evaluations`` output to ``[(evaluator_name, report), ...]``.

       evals < 0.3 returns one report per evaluator, in ``evaluators`` order;
       evals >= 0.3 returns a single report whose rows carry ``cases[i]["evaluator"]``.
       """
       if isinstance(result, list):
           return list(zip(names, result, strict=True))
       ...  # agrupar índices por cases[i]["evaluator"] y armar un sub-reporte por evaluator con
            # model_copy(update=...): cortar scores/test_passes/reasons/detailed_results/cases
            # (y diagnoses/recommendations si existen) y recalcular overall_score
   ```
   - En < 0.3 se usan **los nombres que Loom configuró, por posición**, en lugar de
     `report.evaluator_name` (que es el nombre de clase). Esto también corrige un bug actual: dos
     evaluators del mismo tipo escriben el mismo `{evaluator}.json` y el segundo pisa al primero
     (reproducido en 0.1.13: `['Always', 'Always']`).
   - Para `overall_score`, usar `report_cls.calculate_overall_score` si existe; si no, la media de
     `scores`.
2. **El formato en disco lo define Loom**, no evals. `_save_reports` escribe `evaluator_name`
   explícitamente en cada registro de `results.jsonl` y nombra cada archivo por evaluator. Así el
   historial y `loom evals` (comparación entre runs, `:324-325`) siguen funcionando sin importar la
   versión de evals.
3. `evals_renderer` consume los pares `(name, report)` en lugar de `report.evaluator_name`.

#### F4.2 Nombres de evaluators únicos

Desde 0.3.0, `Experiment._validate_evaluator_names()` lanza `ValueError: Evaluator names must be
unique within an experiment…` si dos evaluators tienen el mismo `get_name()`. Por defecto ese nombre
es el de la clase, así que dos `type: output` con rúbricas distintas fallarían.

**Arreglo**

- Añadir `name: str | None = None` a `EvaluatorConfig` (`schemas/config/evals.py:32`).
- En `_to_evaluator` (`core/loaders/evaluator.py:131`), asignar `name = cfg.name or cfg.type`,
  desambiguar duplicados (`output`, `output_2`, …) y validar unicidad de los nombres explícitos.
- Pasar `name=` al constructor solo si lo acepta (evals ≥ 0.3), con el filtro de F4.3. Esos mismos
  nombres alimentan `split_reports`.

#### F4.3 `include_inputs` (bug conocido, sigue en 1.7.0)

`_to_evaluator` (`core/loaders/evaluator.py:200`) hace `model_dump(exclude_none=True)`, e
`include_inputs` tiene default `True` (no `None`), así que siempre se pasa. `FaithfulnessEvaluator`,
`GoalSuccessRateEvaluator`, `ToolSelectionAccuracyEvaluator` y `ToolParameterAccuracyEvaluator` no
lo aceptan ni en 0.1.13 ni en 1.7.0, y lanzan `TypeError`. Es el `_INCLUDE_INPUTS_BUG` de
`tests/unit/test_evaluator.py:230`, con 4 tests en `xfail(strict=True)`.

**Arreglo**

- Filtrar los kwargs según la firma real del constructor (`inspect.signature`).
- Si el usuario fijó explícitamente un campo no soportado (está en `cfg.model_fields_set`),
  registrar un `warning` que nombre el evaluator y el campo. Si es solo un default, descartarlo sin
  aviso.
- Quitar los 4 `xfail`: con `strict=True` pasarían a XPASS y fallarían, así que el cambio es
  obligatorio.

#### F4.4 Rango de dependencia

Con F4.1–F4.3 implementados: `strands-agents-evals>=0.1.13,<2.0`. Así se soportan las dos formas de
reporte, y el job `lowest-direct` sigue probando 0.1.13. `rich` no necesita cambios.

**Tests (F4)**, sin mockear `run_evaluations`, con un evaluator determinista sin LLM (ver Anexo A):

- 1 y 2 evaluators en 0.1.13 y en 1.7.0. `_save_reports` genera un archivo por evaluator y
  registros con `evaluator_name`.
- Dos evaluators del mismo tipo: no hay `ValueError` en 1.7.0 ni archivos pisados en 0.1.13.
- Los 8 tipos de evaluator se instancian con la config por defecto.

---

### F5 — Graphs sin límites de ejecución · **Baja**

**Afecta:** strands ≥ 1.60.0. `UserWarning: graph has no max_node_executions or execution_timeout
set; execution is unbounded`, emitido desde `core/workflow_builder.py:109`. Un graph con ciclos
puede no terminar nunca; los swarms ya tienen `max_handoffs` y `max_iterations`.

**Arreglo:** exponer en `GraphWorkflowConfig` (`schemas/config/workflow.py:51`) campos opcionales
y llamar a los setters de `GraphBuilder` solo si vienen definidos. Los cuatro setters existen con la
misma firma en 1.34.1 y 1.62.0.

```python
max_node_executions: int | None = Field(default=None, ge=1)    # builder.set_max_node_executions(n)
execution_timeout: float | None = Field(default=None, gt=0)    # builder.set_execution_timeout(s)
node_timeout: float | None = Field(default=None, gt=0)         # builder.set_node_timeout(s)
reset_on_revisit: bool | None = None                           # builder.reset_on_revisit(flag)
```

**Decisión abierta:** ¿aplicar un default seguro (p. ej. `max_node_executions: 50`) o mantener
`None` para no cambiar el comportamiento actual? Propuesta: mantener `None` en esta rama y
documentar los campos en `docs/guides/workflows.md`, junto al ejemplo de `max_handoffs`.

**Tests:** el builder llama a cada setter cuando el campo está definido, y no aparece el
`UserWarning` cuando hay algún límite.

---

### F6 — Puntos ciegos en tests y CI · **Alta (proceso)**

La suite pasa en verde con F1, F2 y F4 porque mockea justo los puntos de integración:

- `tests/unit/test_mcp.py:70-71` reemplaza `_build_transport` por `lambda s: lambda: None`.
- `tests/unit/test_loom_evals.py:281`, `:295` y `:310` fijan `run_evaluations.return_value` a una
  lista.
- `test_bidi.py` no cubre la combinación `kind: bidi` + `tool_executor` con el `BidiAgent` real.

Por eso el job nocturno `.github/workflows/strands-compat.yml` (modo `latest`, que ya instala
strands 1.62 y evals 1.7) **no habría abierto ningún issue**.

**Arreglo**

1. Ampliar `tests/unit/test_strands_contract.py` (o crear `test_vendor_contract.py`) con los tests
   sin mocks de F1, F2, F3 y F4. Cada uno debe fallar hoy en el entorno C, pasar tras su arreglo y no
   necesitar red ni LLM.
2. Regla para el futuro: cada punto donde Loom llama al vendor tiene al menos un test de contrato
   sin mock. Los tests con mocks quedan para la lógica de Loom.
3. Añadir `windows-latest` a la matriz de `.github/workflows/ci.yml` (al menos una versión de
   Python), más el guard de rutas de F0. Hoy todos los jobs corren en `ubuntu-latest`.
4. `strands-compat.yml` puede quedar como está: el modo `latest` ya actualiza strands y evals
   ignorando los pins. Su valor depende del punto 1.

---

### F7 — Menores · **Baja**

- **Fallback muerto:** `strands.agent.model_retry.ModelRetryStrategy`
  (`adapters/strands/__init__.py:23`) no existe en ninguna versión. El símbolo vive en
  `strands.event_loop._retry`, que es privado. La ruta principal `strands.ModelRetryStrategy`
  funciona: eliminar el fallback.
- **Lock:** tras F1–F4, `uv lock --upgrade-package strands-agents --upgrade-package
  strands-agents-evals` para que el entorno de desarrollo use lo mismo que los usuarios
  (strands 1.62.x, mcp 2.x, evals 1.7.x).
- **Documentación:**
  - `docs/guides/workflows.md`: límites de graph (F5).
  - `docs/guides/evals.md`: campo `name` y unicidad (F4.2).
  - `docs/reference/agent-yaml.md`: `tool_executor` no aplica a `kind: bidi` (F2).
  - `docs/contributing.md:51`: mencionar las capacidades nuevas.
  - `README.md`: los enlaces apuntan a `strands-agents/sdk-python`, pero el SDK ahora se desarrolla
    en `strands-agents/harness-sdk` (`strands-py`). Actualizar si corresponde.
- **CHANGELOG:** entrada en `Unreleased` con los arreglos y el cambio de rango de evals.

---

## 6. Cambios de dependencias

| Dependencia | Hoy | Propuesto | Nota |
|---|---|---|---|
| `strands-agents` | `>=1.34,<2.0` | sin cambios | La detección de capacidades cubre todo el rango (§3) |
| `strands-agents-evals` (extra `evals`) | `>=0.1.13,<0.2` | `>=0.1.13,<2.0` | Requiere F4 |
| `mcp` | transitiva | sin pin | `mcp<2` solo como parche temporal (F1.5) |
| `rich` (extra `cli`) | `>=14.3.3` | sin cambios | evals ≥ 1.6 exige `>=15,<16`; verificado con rich 15.0.0 |
| `uv.lock` | strands 1.34.1 / evals 0.1.13 | strands 1.62.x / evals 1.7.x | F7 |

---

## 7. Plan de implementación

Un commit por paso, en formato Conventional Commits (lo exige el hook `commit-msg` del repo):

1. `fix(templates): use a Windows-safe name for the init workspace dir` → **F0**, más el arreglo de
   los tests de `test_dev_reload`. Va primero porque desbloquea el checkout en Windows.
2. `fix(mcp): build http transports through MCPClient(url=) on Strands >= 1.53` → **F1**, más los
   tests de contrato.
3. `fix(build): reject tool_executor on bidi agents when Strands dropped it` → **F2**.
4. `fix(adapters): prefer strands.bidi over the deprecated experimental path` → **F3**.
5. `fix(evals): normalize report shapes and evaluator names across evals versions` → **F4.1–F4.3**,
   quitando los `xfail`.
6. `build(deps): widen strands-agents-evals to <2.0 and refresh uv.lock` → **F4.4**, **F7**.
7. `feat(workflow): expose graph execution limits` → **F5**, más la documentación.
8. `ci: run the suite on windows-latest and guard against NTFS-invalid paths` → **F6.3**, **F0.4**.
9. `docs: update guides and changelog for Strands 1.62 compatibility` → **F7**.

---

## 8. Criterios de aceptación

- [ ] `uv run poe check` en verde.
- [ ] La suite pasa sin fallos en:
  - `uv sync --group dev --resolution lowest-direct` (strands 1.34.x, mcp 1.x, evals 0.1.13);
  - el lock nuevo (strands 1.62.x, mcp 2.x, evals 1.7.x);
  - **Windows** y Linux.
- [ ] El script del Anexo A imprime `OK` en las tres comprobaciones, en los extremos del rango.
- [ ] `python -W error::DeprecationWarning -c "import loom.adapters.strands"` no falla con
      strands 1.62.
- [ ] No queda ningún `xfail` por `_INCLUDE_INPUTS_BUG`.
- [ ] `git clone` en Windows hace checkout completo, y el wheel construido se instala en Windows.

---

## Anexo A — Script de reproducción (sin mocks ni LLM)

Ejecutar con `uv run python repro.py` en cada entorno. Antes de los arreglos, en el entorno C
imprime `FAIL` en las tres comprobaciones; después debe imprimir `OK`.

```python
import importlib.metadata as m
import warnings

warnings.simplefilter("ignore")
print("strands", m.version("strands-agents"), "| mcp", m.version("mcp"), "| evals", m.version("strands-agents-evals"))

# 1) MCP over HTTP — real loader, no mocks
from pydantic import TypeAdapter

from loom.core.loaders.mcp import get_mcp_clients
from loom.schemas.config.mcp import MCPServerConfig

srv = TypeAdapter(MCPServerConfig).validate_python(
    {"name": "gh", "transport": "http", "url": "https://mcp.example.com", "headers": {"Authorization": "Bearer x"}}
)
try:
    print("[MCP http] OK ->", type(get_mcp_clients([srv])[0]).__name__)
except Exception as e:
    print("[MCP http] FAIL ->", type(e).__name__, str(e).splitlines()[-1][:120])

# 2) Bidi + tool_executor — real builder helper
from loom.core import builder
from loom.core.loaders.tool_executor import get_tool_executor
from loom.schemas.config.agent import AgentConfig

cfg = AgentConfig.model_validate({"name": "voice", "description": "d", "kind": "bidi", "tool_executor": "sequential"})
try:
    builder._build_bidi(cfg, {"tool_executor": get_tool_executor("sequential")})
    print("[Bidi+executor] OK")
except ModuleNotFoundError as e:
    # Strands < 1.57.2: el kwarg se aceptó; falla después, al crear el modelo bidi por defecto.
    print("[Bidi+executor] OK (kwargs aceptados; falta el modelo bidi:", e.name, ")")
except Exception as e:
    # Tras F2 se espera AgentConfigError (error claro), nunca TypeError.
    print("[Bidi+executor]", "OK (friendly error)" if type(e).__name__ == "AgentConfigError" else "FAIL", "->", type(e).__name__, str(e)[:120])

# 3) Evals — real Experiment.run_evaluations + deterministic evaluator
from strands_evals import Case, Experiment
from strands_evals.evaluators import Evaluator
from strands_evals.types import EvaluationOutput


class Always(Evaluator):
    def evaluate(self, data):
        return [EvaluationOutput(score=1.0, test_pass=True, reason="ok")]

    async def evaluate_async(self, data):
        return self.evaluate(data)


legacy = m.version("strands-agents-evals").startswith(("0.1.", "0.2."))
evaluators = [Always(), Always()] if legacy else [Always(name="a"), Always(name="b")]
result = Experiment(cases=[Case(name="c1", input="hi")], evaluators=evaluators).run_evaluations(lambda case: "hello")
try:
    # Antes de F4: el manejo actual de Loom. Después: reemplazar por split_reports(result, names).
    print("[Evals] OK ->", len(result), [r.evaluator_name for r in result])
except Exception as e:
    print("[Evals] FAIL ->", type(e).__name__, str(e)[:120])
```

## Anexo B — Trabajar la rama en Windows antes de F0

Mientras F0 no esté mergeado, el checkout en Windows falla por la carpeta con `|`. Procedimiento
verificado: sparse checkout que excluye solo esa carpeta, más `core.protectNTFS=false` **por
comando** (nunca global, porque esa protección existe para repos no confiables):

```bash
git sparse-checkout set --no-cone '/*' '!/src/loom/templates/init/{{ app*'
git -c core.protectNTFS=false checkout fix/strands-1.62-compat
```

- Resultado: 217 archivos versionados, 210 en disco (los 7 de la carpeta excluida quedan como
  `skip-worktree`) y `git status` limpio.
- `git add`, `git commit` y `git switch -c <nueva>` funcionan sin el flag.
- **Cambiar entre ramas existentes** sí requiere `git -c core.protectNTFS=false switch <rama>`. Sin
  el flag, falla y deja el árbol inconsistente.
- Con este procedimiento, los 7 tests de integración de `loom init` no pueden pasar en Windows
  (falta la plantilla). Son justo los que valida F0.
- Después de mergear F0: `git sparse-checkout disable`.

Alternativa: trabajar desde WSL o Linux, donde no aplica ninguna de estas restricciones.
