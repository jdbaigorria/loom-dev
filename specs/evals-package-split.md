# Especificación: separar evals en el paquete `loom-declarative-evals`

| | |
|---|---|
| **Estado** | Propuesta — decisión tomada: opción B (paquete aparte, mismo repo) |
| **Fecha** | 2026-10-24 |
| **Rama** | `fix/strands-1.62-compat` |
| **Relacionado** | [`strands-1.62-compat.md`](strands-1.62-compat.md): el hallazgo F4 se implementa en el paquete nuevo, después de esta separación |

---

## 1. Motivación

- **Volatilidad.** En el mismo período en que `strands-agents` pasó de 1.34 a 1.62 (sin cambio
  mayor), `strands-agents-evals` pasó de 0.1 a 1.7 y cambió el formato del reporte. F4 es la parte
  más grande de la especificación de compatibilidad. Separar evals deja al core con una sola
  promesa de compatibilidad: Strands.
- **Alcance.** Loom se define como librería de *build* ("Execution belongs to the caller", README).
  Evals es un *runner*: ejecuta agentes con `run_dev`, guarda resultados y compara corridas.
- **Costo bajo.** El acoplamiento ya es mínimo (§2). El core solo toca evals en 5 puntos, todos
  opcionales o lazy.

Opciones descartadas: (A) reemplazar la capa por la CLI `strands-evals run --agent` se pierden el
historial, `compare`, `regression` y `failures`, que se usan; (C) repo separado no compensa hasta
que la interfaz esté estable.

---

## 2. Inventario actual

### 2.1 Lo que se mueve

| Hoy | Destino | Líneas |
|---|---|---|
| `src/loom/loom_evals.py` (`LoomEvals`) | `loom_evals/runner.py` | 402 |
| `src/loom/core/loaders/evaluator.py` | `loom_evals/loader.py` | 216 |
| `src/loom/services/evals_service.py` | `loom_evals/service.py` | 146 |
| `src/loom/cli/commands/evals.py` | `loom_evals/cli.py` | 121 |
| `src/loom/cli/renders/evals_renderer.py` | `loom_evals/render.py` | 116 |
| `src/loom/schemas/config/evals.py` | `loom_evals/schemas.py` | 106 |
| `src/loom/adapters/strands/evals.py` (ACL de `strands_evals`) | `loom_evals/adapters/strands_evals.py` | 55 |
| `src/loom/templates/evals/evals.yml.j2` | `loom_evals/templates/evals.yml.j2` | — |
| `EvalsError`, `EvalsNotFoundError`, `EvalsAlreadyExistsError`, `EvalsRunError` (`src/loom/core/exceptions.py:96-130`) | `loom_evals/exceptions.py` | — |

Las excepciones `Evals*` no forman parte de `loom/errors.py` (la API pública de errores) y solo las
usan los módulos de evals, así que se mueven sin dejar alias.

### 2.2 Tests que se mueven (148 de 662)

| Hoy | Destino | Tests |
|---|---|---|
| `tests/unit/test_loom_evals.py` | `packages/loom-evals/tests/test_runner.py` | 35 |
| `tests/unit/test_evaluator.py` | `…/tests/test_loader.py` | 26 |
| `tests/unit/test_evals_service.py` | `…/tests/test_service.py` | 14 |
| `tests/unit/test_schemas.py:440-end` (`TestCase`, `TestEvaluator`, `TestExperiment`) e imports `:11-13` | `…/tests/test_schemas.py` | 55 |
| `tests/unit/test_cli.py:622-825` (`TestCliEvals`) | `…/tests/test_cli.py` | 17 |
| `tests/unit/test_adapters_strands.py:46-48` (`test_all_eval_symbols_resolve`) | `…/tests/test_adapter.py` | 1 |

En el core quedan **514**. Además, `test_resolves_submodule_when_attr_absent`
(`test_adapters_strands.py:64-67`) usa `strands_evals.extractors.tools_use_extractor` como ejemplo
de submódulo. Debe quedarse en el core y cambiar el ejemplo por un submódulo de `strands` (p. ej.
`strands.tools.decorator`), para que los tests del core no dependan de evals. Lo mismo vale para el
import de `evals` en `test_adapters_strands.py:18`.

### 2.3 Lo que se queda en el core: el contrato de plugins

Evals consume esta superficie del core. A partir de esta separación pasa a ser **API pública para
plugins**: se documenta y se protege con un test de contrato en el core (§4.6).

| Símbolo | Uso en evals |
|---|---|
| `loom.dev.run_dev(name, query, session, *, extras, env, kind) -> DevRun` | Ejecuta cada caso |
| `DevRun.response.answer`, `.response.metadata.total_tokens`, `.response.metadata.response_time_ms`, `DevRun.agent` (`strands.Agent`, con `.messages`) | Salida, métricas y trayectoria |
| `loom.core.paths.build_workspace_paths()` → `.eval_file(name)`, `.eval_dir(name)`, `.eval_results_dir(name)` | Layout del workspace |
| `loom.schemas.context.LoomSession` | Sesión por caso |
| `loom.utils.loaders.load_config` | Carga de `evals.yml` |
| `loom.core.exceptions.LoomError`, `AgentNotFoundError` | Base de errores y agente inexistente |
| `loom.utils.ui.console`, `print_error`, `print_hint`, `print_success`, `print_warning` | Salida de la CLI |
| `loom.adapters.strands.resolve`, `LoomStrandsCompatError` | ACL propia de `strands_evals` |

El layout del workspace (`warp/agents/<agent>/evals/evals.yml` y `evals/results/`) sigue
perteneciendo al core: `WorkspacePaths.eval_*` y sus tests (`test_core.py:761-776`) no se mueven.
Así el formato en disco no cambia.

### 2.4 Lo que se elimina o cambia en el core

- `src/loom/cli/cli.py:44-52`: el `try/except ImportError` que registra `loom evals` se reemplaza
  por descubrimiento de plugins (§4.3). **Bug de diseño actual:** `LoomStrandsCompatError` hereda
  de `ImportError`, así que si la ACL de evals no resuelve, el comando `loom evals` **desaparece
  en silencio** en lugar de mostrar el error.
- `src/loom/__init__.py:22,49,53,81-86`: el export lazy de `LoomEvals` pasa a ser un shim deprecado
  (§4.4).
- `src/loom/core/paths/assets.py:14` (`EVALS_TEMPLATES`): se elimina.
- `src/loom/adapters/__init__.py:4`: el docstring deja de mencionar `strands_evals`.
- `pyproject.toml`: `strands-agents-evals` deja de ser dependencia del core (§4.2).

---

## 3. Decisiones de diseño

| # | Decisión | Elección | Motivo |
|---|---|---|---|
| D1 | Ubicación | Workspace de uv en el mismo repo: el core sigue en la raíz y el paquete nuevo va en `packages/loom-evals/` | Cero movimiento del core; cambios atómicos entre ambos lados mientras la interfaz se estabiliza; un solo CI y un solo sitio de docs |
| D2 | Nombres | Distribución `loom-declarative-evals`, import `loom_evals` | `loom` es un paquete regular (tiene `__init__.py`), así que otra distribución no puede aportar `loom.evals` sin convertirlo en namespace package. Eso rompería `loom/__init__.py` y se descarta |
| D3 | CLI | Plugin por *entry point*, grupo `loom.cli`: `evals = "loom_evals.cli:app"` | Mecanismo estándar; el core no sabe nada de evals; sirve para futuros plugins |
| D4 | Plugin roto | Se registra igual, con un comando que muestra el error y sale con 1. Nunca se oculta | Corrige el bug de §2.4 |
| D5 | Compatibilidad | `loom-declarative[evals]` queda como alias que instala el paquete nuevo; `from loom import LoomEvals` funciona con `DeprecationWarning`; los comandos y flags de `loom evals` y el formato en disco no cambian | Migración sin fricción para los usuarios |
| D6 | Versionado | **Lockstep** durante 1.0.x: misma versión y un solo tag `v*` que construye ambos. El paquete nuevo declara `loom-declarative[cli]>=1.0.0rc1,<2` (rango, no pin exacto) | Una sola matriz de compatibilidad mientras el contrato §2.3 madura |
| D7 | Backend de build | setuptools, igual que el core | Consistencia; el `package-data` de plantillas ya está resuelto así en el core |

**Decisiones abiertas**

- **O1 — Retiro de los shims de D5:** ¿en 1.0.0 GA (aún estamos en rc) o en 2.0? Propuesta:
  mantenerlos hasta 1.1 y retirarlos con aviso en el CHANGELOG.
- **O2 — Desacoplar versiones (D6):** cuando la cadencia de evals lo pida, pasar a tags `evals-v*`
  independientes.

**Verificado con un workspace mínimo en uv 0.12.23:**

- `uv lock` resuelve el ciclo `core[evals] → evals → core[cli]`.
- `importlib.metadata.entry_points(group=…)` descubre el plugin.
- `uv build --all-packages` construye ambos wheels.
- `uv pip install "core[evals]" --find-links dist` desde los wheels instala los dos paquetes.

---

## 4. Diseño

### 4.1 Estructura

```
packages/loom-evals/
├── pyproject.toml
├── README.md
├── src/loom_evals/
│   ├── __init__.py              # API pública: LoomEvals, get_experiment, schemas
│   ├── runner.py                # LoomEvals
│   ├── loader.py                # get_experiment, _to_evaluator, _to_case
│   ├── service.py               # new_evals, run_evals, …
│   ├── schemas.py               # CaseConfig, EvaluatorConfig, ExperimentConfig
│   ├── exceptions.py            # EvalsError (subclase de loom.core.exceptions.LoomError) y derivadas
│   ├── cli.py                   # Typer app → entry point loom.cli:evals
│   ├── render.py
│   ├── adapters/
│   │   └── strands_evals.py     # ACL: el único lugar que importa strands_evals
│   └── templates/
│       └── evals.yml.j2
└── tests/
```

### 4.2 `pyproject.toml`

**Paquete nuevo** (`packages/loom-evals/pyproject.toml`):

```toml
[project]
name = "loom-declarative-evals"
version = "1.0.0rc1"                       # lockstep con loom-declarative (D6)
description = "Evaluation runner and `loom evals` CLI plugin for Loom"
requires-python = ">=3.11"
dependencies = [
    "loom-declarative[cli]>=1.0.0rc1,<2",  # typer, rich y jinja2 vienen del extra cli
    "strands-agents-evals>=0.1.13,<0.2",   # F4 lo amplía a <2.0 (strands-1.62-compat.md §F4.4)
]

[project.entry-points."loom.cli"]
evals = "loom_evals.cli:app"

[tool.uv.sources]
loom-declarative = { workspace = true }

[tool.setuptools.packages.find]
where = ["src"]

[tool.setuptools.package-data]
loom_evals = ["templates/*"]

[build-system]
requires = ["setuptools>=61.0"]
build-backend = "setuptools.build_meta"
```

**Core** (`pyproject.toml` raíz), cambios:

```toml
[project.optional-dependencies]
evals = ["loom-declarative-evals>=1.0.0rc1,<2"]   # alias de compatibilidad (D5)
all = ["loom-declarative[cli,evals,aws,tools]"]   # sin cambios

[tool.uv.workspace]
members = ["packages/*"]

[tool.uv.sources]
loom-declarative-evals = { workspace = true }
```

- **ruff:** el paquete no define `[tool.ruff]`, así que lo rige la configuración raíz.
  - `known-first-party = ["loom", "loom_evals"]`.
  - Los dos `banned-api` (`strands` y `strands_evals`) quedan en la raíz.
  - En `per-file-ignores`, sumar `"packages/loom-evals/src/loom_evals/adapters/*" = ["TID251"]`.
- **mypy:** `mypy_path = "src:packages/loom-evals/src"`; la tarea `type` revisa ambos paquetes.
- **pytest:** `testpaths = ["tests", "examples", "packages/loom-evals/tests"]`.
- **coverage:** `source = ["src/loom", "packages/loom-evals/src/loom_evals"]`.
- **poe:** `format`, `lint` y `test` incluyen `packages/`.

### 4.3 Descubrimiento de plugins en la CLI

Esto reemplaza `src/loom/cli/cli.py:44-52`:

```python
from importlib.metadata import entry_points

def _mount_broken_plugin(app: Typer, name: str, exc: BaseException) -> None:
    """Mount ``name`` as a command that reports why the plugin failed to load.

    A plain command (not a group) that swallows every argument, so ``loom evals``,
    ``loom evals run x --failures`` and ``loom evals --help`` all show the real cause.
    """

    @app.command(
        name=name,
        help=f"(unavailable) the '{name}' plugin failed to load",
        context_settings={"allow_extra_args": True, "ignore_unknown_options": True, "help_option_names": []},
    )
    def _report() -> None:
        print_error(f"The '{name}' plugin could not be loaded: {exc}")
        print_hint("Run `loom doctor` for details, or reinstall the plugin package.")
        raise Exit(1)


# CLI plugins (e.g. `loom evals` from loom-declarative-evals) advertise a Typer app under
# the `loom.cli` entry-point group. A plugin that fails to load is still mounted, as a
# command that reports the error — never silently dropped.
for _ep in entry_points(group="loom.cli"):
    try:
        app.add_typer(_ep.load(), name=_ep.name)
    except Exception as exc:  # any load failure, including LoomStrandsCompatError
        _mount_broken_plugin(app, _ep.name, exc)
```

Verificado con Typer: un *grupo* con solo un `callback` no sirve. `loom evals run x` resuelve
primero el subcomando y termina con un error de uso (exit 2) en vez del error real. El comando con
`allow_extra_args` + `ignore_unknown_options` + `help_option_names: []` muestra el error en las
tres formas de invocación. El texto de ayuda usa paréntesis porque Rich interpreta `[…]` como
markup y lo oculta.

`loom doctor` lista los plugins instalados con nombre, distribución, versión y estado (OK o el
error de carga).

### 4.4 Shim de `LoomEvals` (D5)

En `src/loom/__init__.py`:

```python
def __getattr__(name: str):
    if name == "LoomEvals":
        warnings.warn(
            "`from loom import LoomEvals` is deprecated; use `from loom_evals import LoomEvals`.",
            DeprecationWarning,
            stacklevel=2,
        )
        if importlib.util.find_spec("loom_evals") is None:
            raise ImportError(
                "LoomEvals moved to the 'loom-declarative-evals' package: "
                "pip install loom-declarative-evals"
            )
        from loom_evals import LoomEvals  # real import errors propagate unchanged

        return LoomEvals
    raise AttributeError(f"module 'loom' has no attribute {name!r}")
```

Se usa `find_spec` en vez de `try/except ImportError` para no confundir "no instalado" con un error
real de compatibilidad, que también es un `ImportError` (§2.4).

El módulo `loom.loom_evals` desaparece sin shim. Solo lo menciona `docs/contributing.md`, y el
proyecto está en pre-release.

### 4.5 ACL de `strands_evals`

`loom_evals/adapters/strands_evals.py` conserva el contenido actual de
`loom/adapters/strands/evals.py`. Solo cambia el import de `resolve`, que pasa a ser
`from loom.adapters.strands import resolve` (API pública del core, §2.3). Los arreglos de F4
(`split_reports`, filtrado de kwargs por firma) viven acá.

### 4.6 Guardas de la separación

1. **El core no importa evals.** Test en el core: tras `import loom` y `from loom.cli.cli import
   app`, `"strands_evals"` y `"loom_evals"` no están en `sys.modules`.
2. **Contrato de plugins.** Test en el core que verifica que cada símbolo de §2.3 existe y conserva
   la firma: parámetros de `run_dev`, campos de `DevRun` y métodos de `WorkspacePaths`. Si un
   cambio del core rompe el plugin, falla en el core, no en el plugin.
3. **Job de CI "core sin evals":** `uv sync --group dev --extra cli --extra aws --extra tools`.
   Dentro de un workspace, `uv sync` instala solo el paquete raíz. Con ese entorno corre
   `pytest tests examples` y comprueba que `loom --help` no lista `evals`.
4. **Smoke de wheels:** se construyen ambos. Se verifica que `loom-declarative-evals` incluya
   `loom_evals/templates/evals.yml.j2`, y que tras instalarlo `loom evals --help` funcione, igual
   que el chequeo de plantillas actual de `ci.yml`.

---

## 5. Cambios en CI, release y docs

| Archivo | Cambio |
|---|---|
| `.github/workflows/ci.yml` | `ruff check` y `format --check` sobre `src/ tests/ packages/` (`:27`, `:30`); `uv sync --all-packages --group dev --all-extras` (`:54`, `:83`); `pytest --cov=loom --cov=loom_evals` (`:57`); mypy sobre ambos (`:86`); `uv build --all-packages` y smoke de ambos wheels (`:108-130`); job nuevo "core sin evals" (§4.6.3) |
| `.github/workflows/release.yml` | `uv build` → `uv build --all-packages` (los dos artefactos van al mismo GitHub Release) |
| `.github/workflows/strands-compat.yml` | `uv sync … --all-packages` en ambos modos, para que el canario cubra también el paquete de evals |
| `CONTRIBUTING.md` / `docs/contributing.md` | Setup con `uv sync --all-packages --all-extras --group dev`; árbol del repo (`docs/contributing.md:43,47`); cómo escribir un plugin `loom.cli` |
| `docs/installation.md:19` | `[evals]` como alias, con `pip install loom-declarative-evals` como forma recomendada |
| `docs/guides/evals.md:10` | Instalación con el paquete nuevo; `from loom_evals import LoomEvals` |
| `docs/reference/python-api.md:14,225-240` | `LoomEvals` desde `loom_evals`; nueva sección "Contrato de plugins" (§2.3) |
| `docs/reference/cli.md:146-148` | `loom evals` lo provee `loom-declarative-evals` |
| `README.md:17,44,144-148,336-338` | Extras e instalación |
| `CHANGELOG.md` | `Unreleased`: paquete nuevo, alias `[evals]`, deprecación de `from loom import LoomEvals` |

---

## 6. Plan de implementación

Cada commit deja la suite en verde, en formato Conventional Commits:

1. `build: turn the repo into a uv workspace with an empty loom-declarative-evals package`
2. `feat(cli): discover CLI plugins via the loom.cli entry-point group`. El descubrimiento entra
   primero, sin plugins; `loom evals` sigue registrado por el mecanismo viejo.
3. `refactor(evals): move evals into loom-declarative-evals`. Commit **atómico**: `git mv` de los
   módulos, plantillas y tests de §2.1 y §2.2; reescritura de imports; entry point; shim (§4.4);
   alias `[evals]`; eliminación del registro viejo en `cli.py`. Usar `git mv` sin reescribir
   contenido de más, para que `git log --follow` y la detección de renombres conserven la
   historia.
4. `test: guard the core against importing evals and pin the plugin contract` (§4.6.1, §4.6.2).
5. `ci: lint, type-check, test and build both packages; add a core-without-evals job` (§4.6.3,
   §4.6.4, §5).
6. `docs: document loom-declarative-evals and the plugin contract` (§5).

Después, F4 de [`strands-1.62-compat.md`](strands-1.62-compat.md) se implementa en el paquete
nuevo.

---

## 7. Criterios de aceptación

- [ ] Se recolectan 662 tests (514 en el core y 148 en el paquete), con el mismo resultado que antes
      de la separación.
- [ ] `loom evals new|run|compare|failures|regression` se comportan igual. Los tests de CLI movidos
      solo cambian el destino de los `patch` (`loom.cli.commands.evals.*` → `loom_evals.cli.*`).
- [ ] Con el core instalado sin evals, la suite del core pasa, `loom --help` no lista `evals` y no
      se importa `strands_evals` ni `loom_evals`.
- [ ] `pip install "loom-declarative[evals]"` instala ambos paquetes. `from loom import LoomEvals`
      funciona y emite `DeprecationWarning`.
- [ ] Un plugin que falla al cargar aparece como comando que reporta el error, y `loom doctor` lo
      lista.
- [ ] `uv build --all-packages` genera ambos wheels; el de evals incluye la plantilla.
- [ ] `git log --follow packages/loom-evals/src/loom_evals/runner.py` muestra la historia de
      `src/loom/loom_evals.py`.
- [ ] `pyproject.toml` del core ya no declara `strands-agents-evals`.
