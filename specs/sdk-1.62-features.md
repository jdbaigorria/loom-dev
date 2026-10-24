# Especificación: exponer en el YAML las capacidades nuevas del SDK de Strands

| | |
|---|---|
| **Estado** | Propuesta |
| **Fecha** | 2026-10-24 |
| **Rama** | `fix/strands-1.62-compat` |
| **Prerrequisitos** | [`strands-1.62-compat.md`](strands-1.62-compat.md) F0–F3 (Loom funcionando en Strands ≥ 1.57.2) y [`evals-package-split.md`](evals-package-split.md) |
| **Orden** | Después de los dos specs anteriores |

---

## 1. Motivación

Desde la 1.34 (el piso de Loom), `strands.Agent` ganó **9 parámetros** que Loom no expone. Además,
`plugins` ya existía en 1.34 y Loom solo lo detecta (`capabilities.has_plugins()`) sin permitir
declararlo.

La comparación con `strands-harness` (0.3.2, Beta) mostró que el Harness no aporta capacidades
nuevas. Activa por defecto estas mismas piezas del SDK, las conecta entre sí y suma un prompt de
sistema ajustado. Por eso Loom puede ofrecerlas **de forma declarativa, sin depender del Harness**
(un paquete 0.x) **y sin reimplementar nada**: del YAML a objetos del SDK, igual que hoy con
`session_manager` y `conversation_manager`.

| Parámetro de `Agent` | Desde strands | Para qué sirve (según la documentación del SDK) | Hoy en Loom |
|---|---|---|---|
| `plugins` | ≤ 1.34.0 | Extensiones con acceso al agente: skills, offload de contexto, `goal`, steering… | Solo detección |
| `context_manager` | 1.43.0 | `"auto"` (trunca resultados de tools y resume al 85 % de uso), `"agentic"` (lo maneja el modelo) o un pipeline propio | No |
| `interventions` | 1.43.0 | Controles por evento: `Proceed`, `Deny`, `Guide`, `Confirm`, `Transform`. Incluye HITL y Cedar | No |
| `checkpointing` | 1.43.0 | Pausa en los límites de ciclo y devuelve `stop_reason="checkpoint"` (**experimental**) | No |
| `memory_manager` | 1.44.0 | Memoria entre sesiones: extracción, búsqueda e inyección en contexto | No |
| `sandbox` | 1.44.0 | Entorno donde corren comandos y archivos (Docker, SSH). Sin él, todo corre en el host **sin aislamiento** | No |
| `storage` | 1.52.0 | Backend por defecto para los subsistemas que no definen el suyo (sesión, contexto) | No |
| `background_tasks` | 1.55.1 | El modelo puede correr tools en segundo plano | No |
| `aux_model` | 1.58.0 | Modelo para las llamadas secundarias: resumen, extracción de memoria, clasificador de HITL, steering, juez de `goal` | No |
| `baggage_attributes` | 1.60.0 | Atributos de *baggage* de OTel por invocación | No |
| `trace_attributes` | ≤ 1.34.0 | Atributos de traza de OTel | No |

Las versiones se obtuvieron escaneando la firma de `Agent.__init__` en todos los wheels publicados
desde 1.34.0 hasta 1.62.0. La forma de cada configuración se verificó en 1.62.0. Como pudo cambiar
entre versiones intermedias, cada loader se prueba en los extremos del rango (§6).

---

## 2. Principios de diseño

1. **Nada activo por defecto.** Igual que hoy (`session: None`, `conversation: none`), cada
   capacidad se activa solo si se declara. Es la diferencia de fondo con el Harness.
2. **Los mismos patrones que ya usa Loom:**
   - Presets por nombre corto (como `conversation: none`).
   - Entradas `nombre` o `{nombre: params}` de una sola clave (como `hooks`).
   - Una vía libre `import_path` + `params` (como `model`, `session` y `conversation` custom).
   - Para listas (`plugins`, `interventions`), el orden de resolución de los hooks: **integrado → ruta
     con puntos → archivo local**.
3. **Detección por capacidades en la ACL.** Un helper `capabilities.agent_accepts(param)` (con
   `inspect.signature(Agent.__init__)` y caché) decide si se puede pasar cada parámetro. Si el YAML
   declara algo que la versión instalada no soporta, Loom lanza `AgentConfigError` con
   `tip="Requiere strands-agents >= X"`. Nunca debe llegar a ser un `TypeError` del SDK.
4. **Solo rutas públicas del SDK.** Por ejemplo, `ContextManagerConfig` vive en
   `strands._context_manager.types`, que es privado. Para contexto, Loom pasa presets en texto o
   dicts (el SDK acepta un dict como `ContextManagerConfig`) y no importa la clase.
5. **Validar lo que el SDK ignora en silencio.** Con `context_manager` definido, el SDK ignora
   `conversation_manager` sin avisar (§3.2). Loom lo detecta al cargar.
6. **Ubicación:** lo que define el *comportamiento* de un agente va en su YAML; la
   *infraestructura* compartida (sandbox, storage, telemetría) va en `app.yml`, como hoy `session` y
   `telemetry`.
7. **Bidi:** en 1.62, `BidiAgent` solo acepta `storage` de esta lista. Los demás campos se rechazan
   con `kind: bidi`, mediante un validador del schema.

---

## 3. Diseño por capacidad

### 3.1 `plugins` (YAML del agente) · desde ≤ 1.34

```yaml
plugins:
  - skills: { skills: ./skills }                 # AgentSkills; rutas relativas a config/ del agente
  - context_offloader: { max_result_tokens: 2500, preview_tokens: 1000 }
  - goal: { goal: "La respuesta incluye el número de ticket", max_attempts: 3 }
  - my_pkg.plugins.AuditPlugin                   # ruta con puntos
  - audit                                        # local: warp/plugins/audit.py
```

**Plugins integrados** (en el registro de Loom, rutas públicas verificadas en 1.62):

| Nombre | Clase del SDK | Parámetros principales |
|---|---|---|
| `skills` | `strands.vended_plugins.skills.AgentSkills` | `skills` (directorio, `SKILL.md`, URL o lista), `max_resource_files`, `strict` |
| `context_offloader` | `strands.vended_plugins.context_offloader.ContextOffloader` | `max_result_tokens`, `preview_tokens`, `include_retrieval_tool`, `evict_after_cycles` |
| `goal` | `strands.vended_plugins.goal.GoalLoop` | `goal`, `max_attempts`, `timeout`; `judge.model` en formato de modelo de Loom |

`context_injector` y `steering` necesitan callables (p. ej. `render_content`), así que **no** entran
en el registro. Se usan con una ruta con puntos a una fábrica.

- **Validación:** la instancia debe ser un `sx.Plugin`. El archivo local sigue la misma convención que
  los hooks: una clase PascalCase derivada del nombre del archivo, en `warp/plugins/` (agregar
  `WorkspacePaths.plugins_dir`).
- **Nota:** las instancias de plugins se crean en cada `build`. No se comparten entre agentes.

### 3.2 `context` → `context_manager` (YAML del agente) · desde 1.43

```yaml
context: auto            # auto | agentic | off
# pipeline propio (dict pasado tal cual al SDK):
context:
  strategies: [...]
  stash: true
# vía libre:
context:
  import_path: my_pkg.MyContextManager
  params: {}
```

- **Mapeo:** `auto`/`agentic` → el mismo texto; `off` → `False`; dict con `strategies`/`stash` →
  dict; `import_path` → instancia.
- **Conflicto con `conversation`:** con `context_manager` definido, el SDK **ignora en silencio** el
  `conversation_manager`. Hoy Loom siempre pasa uno, porque `conversation: none` (el default de
  `app.yml`) se resuelve como `NullConversationManager` (`config/profiles.py:64`). Las reglas usan
  la conversación **resuelta** del agente: la propia si la declara, y si no la de `app.yml` (ver
  [`strands-1.62-compat.md`](strands-1.62-compat.md) F8):
  - Si el agente declara `context` y su conversación resuelta es `none` o `None`, **no** se pasa
    `conversation_manager`.
  - Si es otra estrategia, se lanza `AgentConfigError`: son excluyentes, y hay que elegir `context` o
    `conversation`.
- **Modelos stateful:** el SDK lanza `ValueError` si recibe `context_manager` o `conversation_manager`
  con un modelo `stateful`. Ver §7, hallazgo H1.

### 3.3 `memory` → `memory_manager` (YAML del agente) · desde 1.44

```yaml
memory:
  stores:
    - file: { name: notas, description: "Hechos del usuario", writable: true }
    - bedrock_kb:
        name: politicas
        config: { knowledge_base_id: ABC123XYZ }   # BedrockKnowledgeBaseConfig del SDK
        scope: "{user_id}"                          # ver decisión abierta O1
        max_search_results: 5
  search_tool: true      # search_tool_config (default del SDK: true)
  add_tool: false        # add_tool_config (default del SDK: false)
  injection: true        # injection (default del SDK: true)
```

- **Mapeo:**
  - `file` → `strands.vended_memory_stores.FileMemoryStore(**cfg)`.
  - `bedrock_kb` → `strands.vended_memory_stores.bedrock_knowledge_base.BedrockKnowledgeBaseStore`.
    Su configuración admite `name`, `description`, `max_search_results`, `writable`, `extraction`,
    `config`, `scope`, `filter`, `access_control_list`, `min_score` y `max_score`.
  - Todo se arma como `strands.memory.MemoryManager(stores, search_tool_config, add_tool_config,
    injection)`.
  - También hay vía libre `import_path` para un `MemoryStore` propio.
- **Extracción:** usa el `model` de `extraction` si se declara; si no, `aux_model` (§3.8), y si no,
  el modelo principal. Es el orden de precedencia del propio SDK.
- **Relación con `builtin.kb`:** la tool `builtin.kb` de Loom consulta una KB *cuando el modelo lo
  decide*. El store `bedrock_kb` *inyecta* resultados antes de cada turno y puede *escribir*
  (`writable`). Son complementarios; la documentación debe explicar cuándo usar cada uno.
- **Credenciales por ejecución:** igual que `builtin.kb` (commit `151e4d6`), el store `bedrock_kb`
  debe recibir el `boto_session` del overlay de cada ejecución, para no usar credenciales del entorno.

### 3.4 `interventions` (YAML del agente) · desde 1.43

```yaml
interventions:                       # el orden importa: las más baratas primero (recomendación del SDK)
  - hitl:
      allowed_tools: [buscar_factura]  # no piden aprobación
      classifier: true                 # clasificador de riesgo con LLM (usa aux_model)
      ask: stdio                       # o ruta con puntos a un callback
  - cedar:                             # requiere el extra strands-agents[cedar] (cedarpy)
      policies: ./policies/billing.cedar
      entities: ./policies/entities.json
  - my_pkg.guards.PiiGuard            # InterventionHandler propio
```

- **Integradas:**
  - `hitl` → `strands.vended_interventions.HumanInTheLoop`. Parámetros: `allowed_tools`,
    `classifier`, `enable_trust`, `evaluate_trust`, `evaluate` y `ask`. Los callbacks se dan como ruta
    con puntos.
  - `cedar` → `strands.vended_interventions.cedar.CedarAuthorization`. Parámetros: `policies`
    (obligatorio; texto Cedar o ruta a un `.cedar`), `entities` (lista, JSON o ruta a un `.json`),
    `schema` (texto o ruta a un `.cedarschema`), `tools`, `principal`, `principal_resolver`,
    `context_enricher` y `on_error` (default `"throw"`). Las rutas se resuelven relativas a `config/`
    del agente.
- **Validación:** cada elemento debe ser un `sx.InterventionHandler`. Los nombres de `allowed_tools`
  tienen que existir entre las tools del agente.
- **Extra nuevo de Loom:** `cedar = ["strands-agents[cedar]"]`. Sin él, `cedar` lanza
  `AgentConfigError` con la indicación de instalarlo.
- **A verificar en la implementación:** cómo interactúa HITL fuera de `ask: stdio` con el flujo de
  *interrupts* que Loom ya maneja (`cli/commands/run.py:22`, `AgentResponse.interrupts`).

### 3.5 `sandbox` (`app.yml`, con override por agente) · desde 1.44

```yaml
# app.yml
sandbox:
  docker: { container: loom-runner, working_dir: /work, user: "1000" }
# o
sandbox:
  ssh: { host: runner.internal, working_dir: /srv/agent, identity_file: ~/.ssh/id_ed25519, port: 22 }
# o
sandbox:
  import_path: my_pkg.MySandbox
  params: {}
```

- **Mapeo:** `docker` → `strands.sandbox.docker.DockerSandbox(container, working_dir, user)`;
  `ssh` → `strands.sandbox.ssh.SshSandbox(host, working_dir, identity_file, port, ssh_options,
  allow_unknown_hosts, allow_unsafe_ssh_options)`.
- **Seguridad:**
  - Sin `sandbox`, las tools que lo usan corren en el host **sin aislamiento**
    (`NotASandboxLocalEnvironment`). La documentación debe decirlo explícitamente.
  - Loom **no** cambia los defaults seguros de SSH (`allow_unknown_hosts` y
    `allow_unsafe_ssh_options` quedan en `false`).
- **Construcción:** `DockerSandbox.__init__` solo guarda parámetros y no ejecuta Docker
  (verificado), así que se puede construir en `build` y en tests sin efectos.
- Como `app.yml` es por entorno, `dev` puede usar Docker local y `prod` un runner SSH.

### 3.6 `storage` (`app.yml`) · desde 1.52

```yaml
storage:
  local: { base_dir: .loom/storage }     # default propuesto: dentro de .loom/, no ./.strands/
# o
storage:
  s3: { bucket: my-bucket, prefix: loom/, region_name: us-east-1 }
# o
storage: memory
```

- **Mapeo:** `strands.storage.LocalFileStorage(base_dir, sandbox=…)`, `S3Storage(bucket, prefix,
  region_name, boto_session=…)`, `InMemoryStorage()`.
- **Semántica del SDK:** es el default para los subsistemas que no definen su propio storage (sesión,
  contexto). El storage explícito de cada subsistema siempre gana.
- **Credenciales y sandbox:** `S3Storage` recibe el `boto_session` del overlay por ejecución (como
  el store `bedrock_kb` en §3.3), y `LocalFileStorage` recibe el `sandbox` de §3.5 si existe.
- **Bidi:** es el único campo de este spec que `BidiAgent` acepta en 1.62.

### 3.7 `background_tasks` (YAML del agente) · desde 1.55.1

```yaml
background_tasks: true
# o
background_tasks:
  always: [generar_reporte]        # nombres de tools del agente
  never: [buscar_factura]
  agentic: [exportar_csv]          # el modelo decide
  max_concurrency: 4
  timeout: 120
  wait_for_completion: true
```

- **Mapeo:** `true` → `True`; un dict → `BackgroundTasksConfig`, que es un `TypedDict` y se pasa como
  dict.
- **Validación:** los nombres de `always`, `never` y `agentic` tienen que existir entre las tools del
  agente.

### 3.8 `aux_model` (YAML del agente) · desde 1.58

```yaml
aux_model: economic     # mismo formato que `model`: perfil de profiles.toml o inline
```

- **Mapeo:** se reutiliza `get_model()` del loader de modelos, incluido el overlay de `model_params`
  por ejecución. Así las credenciales del modelo auxiliar coinciden con las del principal.
- **Precedencia del SDK:** el `model=` de cada componente gana a `aux_model`, que gana al `model`
  principal. Con `aux_model`, todas las llamadas secundarias salen del modelo principal de una vez.

### 3.9 `checkpointing` (YAML del agente) · desde 1.43 · **experimental**

```yaml
checkpointing: true
```

Cambia el flujo de control: la invocación puede terminar con `stop_reason="checkpoint"`, y se
reanuda pasando `{"checkpointResume": {"checkpoint": ...}}`. El SDK aclara que el checkpoint **no**
guarda la conversación y que hay que combinarlo con un `SessionManager`.

Loom hoy no lo soporta en `core/response.py` (`build_response`) ni en el loop de `loom agent run`.
**Propuesta:** fase final, detrás de una marca experimental. `AgentResponse` necesitaría un campo
`checkpoint` y el loop de la CLI tendría que manejarlo. Ver decisión abierta O3.

### 3.10 Telemetría: `trace_attributes` y `baggage_attributes` (`app.yml`)

```yaml
telemetry:
  enabled: true
  trace_attributes: { app: billing, team: payments }       # desde ≤ 1.34
  baggage_attributes: { tenant: "${oc.env:TENANT}" }       # desde 1.60
```

- **Mapeo:** se pasan tal cual a `Agent(trace_attributes=…, baggage_attributes=…)`, y se agregan a
  `TelemetryConfig` (`schemas/config/telemetry.py`).
- **Atributos por ejecución:** ver decisión abierta O4.

### 3.11 Menores (ya existen en 1.34; opcionales)

- **`structured_output_prompt`:** ampliar `output` para aceptar `{class: …, prompt: "…"}` además del
  texto actual.
- **`concurrent_invocation_mode`:** no se expone. El default del SDK (`throw`) es el comportamiento
  correcto para Loom.

---

## 4. Cambios transversales

| Área | Cambio |
|---|---|
| **ACL** (`adapters/strands/__init__.py`) | Símbolos opcionales (`optional=True`): `Plugin`, `InterventionHandler`, `MemoryManager`, `FileMemoryStore`, `BedrockKnowledgeBaseStore`, `AgentSkills`, `ContextOffloader`, `GoalLoop`, `HumanInTheLoop`, `CedarAuthorization`, `Sandbox`, `DockerSandbox`, `SshSandbox`, `Storage`, `LocalFileStorage`, `S3Storage`, `InMemoryStorage`. Cada uno con su ruta pública verificada (Anexo A) |
| **Capacidades** (`capabilities.py`) | `agent_accepts(param)` genérico; `snapshot()` lo incluye para cada parámetro de §1, de modo que `loom doctor` muestre qué soporta la versión instalada |
| **Schemas** | `AgentConfig`: `plugins`, `context`, `memory`, `interventions`, `background_tasks`, `aux_model`, `checkpointing`. `AppConfig`: `sandbox`, `storage`. `TelemetryConfig`: `trace_attributes`, `baggage_attributes`. Módulos nuevos en `schemas/config/` |
| **Validadores** | `kind: bidi` rechaza todo salvo `storage`; `context` vs `conversation` (§3.2); los nombres de tools referenciados existen (§3.4, §3.7) |
| **Loaders** (`core/loaders/`) | Módulos nuevos `plugin.py`, `context.py`, `memory.py`, `intervention.py`, `sandbox.py` y `storage.py`, con el mismo estilo que `session.py` y `conversation.py` |
| **Builder** (`core/builder.py:159-185`) | Sumar los parámetros nuevos a `shared_params`/`agent_only` y filtrar los `None` como hoy. Cada uno pasa por `agent_accepts` antes de incluirse |
| **Workspace** | `WorkspacePaths.plugins_dir` (`warp/plugins/`); `loom init` crea la carpeta |
| **Extras** | `cedar = ["strands-agents[cedar]"]` |
| **Docs** | `docs/reference/agent-yaml.md`, `docs/reference/app-yaml.md` y una guía nueva "Memoria, contexto y control" que incluya la advertencia de seguridad de §3.5 |

---

## 5. Plan por fases

Cada fase es independiente, deja la suite en verde y suma su documentación:

| Fase | Contenido | Por qué en este orden |
|---|---|---|
| 1 | `capabilities.agent_accepts` + **`plugins`** (skills, context_offloader, goal, ruta con puntos y local) + **`context`** + **`aux_model`** | Más valor con menos riesgo; no agrega infraestructura |
| 2 | **`storage`** + **`memory`** (file, bedrock_kb) | Memoria necesita definir antes la persistencia y el alcance por usuario (O1) |
| 3 | **`interventions`** (hitl, cedar + extra) | Requiere verificar la interacción con los *interrupts* de Loom |
| 4 | **`sandbox`** + **`background_tasks`** | Infraestructura de ejecución |
| 5 | **Telemetría** (`trace_attributes`, `baggage_attributes`) | Bajo riesgo; puede ir antes si hace falta |
| 6 | **`checkpointing`** (experimental) | Cambia el flujo de respuesta y la CLI |

Commits sugeridos: `feat(agent): declare SDK plugins in agent YAML`, `feat(agent): context
management strategies`, `feat(agent): aux_model for SDK side calls`, `feat(memory): memory stores and
manager`, `feat(app): agent-level storage backend`, `feat(agent): interventions (hitl, cedar)`,
`feat(app): execution sandboxes`, `feat(agent): background tool tasks`, `feat(telemetry): trace and
baggage attributes`, `feat(agent): experimental checkpointing`.

---

## 6. Pruebas

- **Schemas:** formas válidas e inválidas de cada campo, más los validadores cruzados (bidi y
  `context` vs `conversation`).
- **Loaders sin mocks del SDK:** cada uno construye el objeto real de Strands sin red:
  `FileMemoryStore` y `LocalFileStorage` en `tmp_path`, `DockerSandbox` (no ejecuta nada al
  construirse), `AgentSkills` con un `SKILL.md` de prueba, `HumanInTheLoop`. Se mockea solo lo que
  sale a la red, como el cliente de Bedrock.
- **Builder:** un test por capacidad que construye un `Agent` real con `MockModel`
  (`loom.testing`) y verifica que el parámetro llegó.
- **Detección de versión:** en el job `lowest-direct` (strands 1.34.x), cada campo de §1 posterior a
  1.34 lanza `AgentConfigError` con la versión mínima en el `tip`. Ese mismo test pasa a verde en
  1.62.
- **Contrato:** sumar a `test_strands_contract.py` las rutas del Anexo A, como opcionales que deben
  resolver en 1.62.

---

## 7. Hallazgos laterales

- **H1 — Modelos stateful con el `conversation_manager` por defecto.** En 1.62, `Agent.__init__`
  rechaza `conversation_manager`/`context_manager` cuando `model.stateful` es verdadero ("cannot be
  used with a stateful model"). Loom siempre pasa `NullConversationManager` por el default
  `conversation: none`, así que un modelo stateful declarado con `import_path` fallaría al
  construirse. **A verificar:** qué proveedores de Strands son stateful y desde qué versión existe la
  validación. Arreglo propuesto: no pasar `conversation_manager` cuando el modelo es stateful y
  `conversation` sea `none`, y dar un error claro si se declaró otra estrategia.
- **H2 — Sin sandbox, ejecución en el host.** Hoy no afecta a Loom, porque no expone las tools del
  SDK que ejecutan comandos (`shell`, `python_repl`, `file_editor`…). Si en el futuro se exponen, deben
  requerir `sandbox` o una confirmación explícita.

---

## 8. Decisiones abiertas

- **O1 — Memoria por usuario.** En Loom, las sesiones ya llevan `LoomSession.user_id`. Si los stores
  no se separan por usuario, la memoria de uno se filtra a otro. Propuesta: placeholders
  `{user_id}`/`{session_id}` en los valores de texto de la configuración de stores (p. ej.
  `scope: "{user_id}"`, o el directorio de `file`), que se resuelven en `build` con la sesión.
  Alternativa: un store por usuario, armado por el llamador.
- **O2 — Defaults a nivel app.** ¿Permitir `plugins` e `interventions` en `app.yml` para todos los
  agentes (p. ej. un Cedar global), combinados con los de cada agente?
- **O3 — `checkpointing`.** ¿Implementarlo ahora detrás de una marca, o esperar a que salga de
  `strands.experimental`?
- **O4 — Atributos de telemetría por ejecución.** ¿Agregar automáticamente `session.id`/`user.id` de
  `LoomSession` a `trace_attributes`/`baggage_attributes`? `strands-evals` ya usa `session.id` como
  baggage para separar trazas por caso.
- **O5 — `kind: harness`.** Fuera de alcance acá. Este spec cubre la vía nativa del SDK. La
  integración con `strands-harness` solo aportaría su prompt ajustado y su conjunto de tools para
  asistentes autónomos, y se reevalúa cuando el Harness pase de 0.x.

---

## 9. Criterios de aceptación

- [ ] Cada campo de §3 se puede declarar, se valida al cargar (`loom agent validate`) y llega a
      `Agent(...)` con el objeto correcto del SDK, en strands 1.62.
- [ ] En strands 1.34.x, cada campo posterior a 1.34 da `AgentConfigError` con la versión mínima;
      nunca un `TypeError`.
- [ ] Ningún campo nuevo cambia el comportamiento de un YAML que no lo declara (la suite actual pasa
      sin cambios).
- [ ] `context` junto con una estrategia de `conversation` distinta de `none` → error claro;
      `context` con `conversation: none` → no se pasa `conversation_manager`.
- [ ] `kind: bidi` con cualquier campo salvo `storage` → error claro.
- [ ] `loom doctor` muestra qué capacidades soporta la versión instalada de Strands.
- [ ] La guía nueva incluye la advertencia de seguridad de §3.5.

---

## Anexo A — Rutas públicas verificadas en strands 1.62.0

| Símbolo | Ruta |
|---|---|
| `Plugin` | `strands.plugins.Plugin` (también `strands.Plugin`) |
| `InterventionHandler` | `strands.interventions.handler.InterventionHandler` |
| `MemoryManager` | `strands.memory.MemoryManager` |
| `FileMemoryStore` | `strands.vended_memory_stores.FileMemoryStore` |
| `BedrockKnowledgeBaseStore` | `strands.vended_memory_stores.bedrock_knowledge_base.BedrockKnowledgeBaseStore` |
| `AgentSkills` | `strands.vended_plugins.skills.AgentSkills` |
| `ContextOffloader` | `strands.vended_plugins.context_offloader.ContextOffloader` |
| `GoalLoop` | `strands.vended_plugins.goal.GoalLoop` |
| `HumanInTheLoop` | `strands.vended_interventions.HumanInTheLoop` |
| `CedarAuthorization` | `strands.vended_interventions.cedar.CedarAuthorization` (requiere `cedarpy`) |
| `Sandbox` | `strands.sandbox.Sandbox` |
| `DockerSandbox` | `strands.sandbox.docker.DockerSandbox` |
| `SshSandbox` | `strands.sandbox.ssh.SshSandbox` |
| `Storage`, `LocalFileStorage`, `S3Storage`, `InMemoryStorage` | `strands.storage.*` |
| `BackgroundTasksConfig` | `strands.background_tasks.BackgroundTasksConfig` (`TypedDict`; Loom pasa un dict) |
| `ContextManagerConfig` | `strands._context_manager.types` (**privada**; Loom pasa un dict y no la importa) |
