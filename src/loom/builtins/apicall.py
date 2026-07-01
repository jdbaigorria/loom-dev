"""Built-in HTTP tool (``requests``-based), with two modes.

``make_apicall`` builds a Strands tool that calls a pre-configured HTTP API. The
base URL, static headers and timeout are fixed at construction (closure config,
invisible to the model). Two modes, selected by the presence of ``expose``:

- **Domain mode** (``bind`` + ``expose``): the *framework* assembles the request
  from a template; the model only supplies semantic values (e.g. ``name_or_id``).
  ``bind`` is a request template whose ``{param}`` placeholders are filled at call
  time; ``expose`` becomes the ``inputSchema`` the model sees. This yields a
  narrow, domain-shaped tool (``get_pokemon(name_or_id)``) instead of a generic
  HTTP proxy — the recommended path. The model never builds a path, so the whole
  class of path-formatting hallucinations is structurally impossible.

- **Generic mode** (``base_url`` + ``allowed_paths``, no ``expose``): the model
  chooses ``path``/``method``/``body``/``params`` against a glob allow-list. A
  fragile escape hatch for exploring an API; kept for back-compat.

Each instance is renamed via ``name`` so several endpoints can be mounted on one
agent without a tool-name collision (Strands raises on duplicate names). Uses
``requests`` (imported lazily so importing :mod:`loom.builtins` does not require
it). See ``.docs/design-apicall-bind-expose.md`` for the full design.
"""

import fnmatch
import inspect
import logging
import os
import re
from typing import Annotated, Any
from urllib.parse import quote

from loom.adapters.strands import DecoratedFunctionTool, ToolResult, tool

logger = logging.getLogger(__name__)

_WRITE_METHODS = ("POST", "PUT", "PATCH")
_EMPTY_VALUES = (None, "", [], {}, "-", "null", "none", "false")
_JSON_TYPES = ("string", "integer", "number", "boolean", "array", "object")
_PY_TYPES: dict[str, type] = {
    "string": str,
    "integer": int,
    "number": float,
    "boolean": bool,
    "array": list,
    "object": dict,
}
_PLACEHOLDER = re.compile(r"\{(\w+)\}")


def _clean_dict(data: Any) -> Any:
    """Recursively drop empty values from dicts/lists (ported from ``APITools``)."""
    if isinstance(data, dict):
        return {k: c for k, v in data.items() if (c := _clean_dict(v)) not in _EMPTY_VALUES}
    if isinstance(data, list):
        return [c for item in data if (c := _clean_dict(item)) not in _EMPTY_VALUES]
    return data


_MISSING = object()


def _extract(data: Any, in_parts: list[str], out_parts: list[str]) -> Any:
    """Pull the value at the dotted ``in_parts`` and re-key it under ``out_parts``.

    Navigates ``in_parts`` and ``out_parts`` in lock-step. A ``list`` encountered
    at any level is mapped over item by item (so a path like ``"body.codigo"`` over
    ``{"body": [{...}, {...}]}`` projects every element instead of dropping the
    data). Returns :data:`_MISSING` when the source path does not resolve.
    """
    if not in_parts:  # reached the leaf → keep the value verbatim
        return data
    if isinstance(data, list):  # intermediate list → project each item, same paths
        return [r for it in data if (r := _extract(it, in_parts, out_parts)) is not _MISSING]
    if isinstance(data, dict) and in_parts[0] in data:
        inner = _extract(data[in_parts[0]], in_parts[1:], out_parts[1:])
        return {out_parts[0]: inner} if inner is not _MISSING else _MISSING
    return _MISSING


def _deep_merge(a: Any, b: Any) -> Any:
    """Merge two projected fragments: dicts union recursively, lists merge by index."""
    if isinstance(a, dict) and isinstance(b, dict):
        out = dict(a)
        for key, value in b.items():
            out[key] = _deep_merge(a[key], value) if key in a else value
        return out
    if isinstance(a, list) and isinstance(b, list):
        merged = [_deep_merge(x, y) for x, y in zip(a, b)]
        merged.extend(a[len(b):])
        merged.extend(b[len(a):])
        return merged
    return b  # scalar / type mismatch: the later fragment wins


def _project(data: Any, select: list[str]) -> Any:
    """Keep only the ``select`` paths of a response, dropping everything else.

    Each entry is a dotted path navigating nested dicts (``"stats.base"``); the
    result is rebuilt with the same nesting. A path may traverse a ``list`` — the
    projection is then applied to every item (the common pagination shape
    ``{"body": [...]}``). An entry may also rename its leaf with a ``"src:dst"``
    suffix (``"body.codigo:body.id"``); ``src`` and ``dst`` must share the same
    nesting depth. Missing paths are skipped. This is the lever that stops a huge
    upstream payload (a PokéAPI ``moves`` array, sprite URLs, …) from flooding the
    model's context.
    """
    out: Any = {}
    for entry in select:
        src, sep, dst = entry.partition(":")
        in_parts = src.split(".")
        out_parts = (dst if sep else src).split(".")
        fragment = _extract(data, in_parts, out_parts)
        if fragment is not _MISSING:
            out = _deep_merge(out, fragment)
    return out


def _build_session(headers: dict[str, str] | None):
    """Create a ``requests.Session`` with JSON content-type and static headers."""
    import requests  # lazy: only required when this builtin is actually configured

    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    if headers:
        session.headers.update(headers)
    return session


def _execute_request(
    session: Any,
    verb: str,
    url: str,
    *,
    json_body: Any,
    query: dict[str, Any] | None,
    timeout: float,
    clean_response: bool,
    select: list[str] | None = None,
    extra_headers: dict[str, str] | None = None,
) -> ToolResult:
    """Perform one request and shape the response into a ``ToolResult``.

    Shared by both modes so error handling and response cleaning stay identical.
    """
    import requests  # lazy: cached after the first builtin import

    logger.debug("[%s] %s", verb, url)
    try:
        resp = session.request(
            method=verb,
            url=url,
            json=json_body,
            params=query,
            headers=extra_headers or None,
            timeout=timeout,
        )
        resp.raise_for_status()
        try:
            data = resp.json()
        except ValueError:
            return {"status": "success", "content": [{"text": resp.text}]}
        if select:
            data = _project(data, select)
        if clean_response:
            data = _clean_dict(data)
        return {"status": "success", "content": [{"json": data}]}
    except requests.Timeout:
        return {"status": "error", "content": [{"text": f"Timeout calling {url}"}]}
    except requests.HTTPError as exc:
        status = exc.response.status_code if exc.response is not None else None
        text = exc.response.text if exc.response is not None else str(exc)
        return {"status": "error", "content": [{"text": f"HTTP {status}: {text}"}]}
    except requests.RequestException as exc:
        return {"status": "error", "content": [{"text": f"Network error: {exc}"}]}


# ---------------------------------------------------------------------------
# Domain mode (bind / expose)
# ---------------------------------------------------------------------------


class _InjectionError(ValueError):
    """A ``{param}`` value was unsafe or missing at call time."""


def _find_placeholders(template: Any) -> set[str]:
    """Collect every ``{param}`` name from a str / dict / list template."""
    found: set[str] = set()
    if isinstance(template, str):
        found.update(_PLACEHOLDER.findall(template))
    elif isinstance(template, dict):
        for value in template.values():
            found |= _find_placeholders(value)
    elif isinstance(template, list):
        for item in template:
            found |= _find_placeholders(item)
    return found


def _inject_path(template: str, params: dict[str, Any]) -> str:
    """Fill ``{param}`` placeholders in a URL path, URL-encoded and traversal-safe.

    Each value is percent-encoded with ``safe=""`` (so an injected ``/`` cannot
    add a path segment) and rejected if it contains ``..`` (path traversal).
    """

    def repl(match: re.Match[str]) -> str:
        key = match.group(1)
        if key not in params:
            raise _InjectionError(f"missing value for path param '{key}'")
        value = str(params[key])
        if ".." in value:
            raise _InjectionError(f"path param '{key}' contains '..': {value!r}")
        return quote(value, safe="")

    return _PLACEHOLDER.sub(repl, template)


#: Sentinel returned by ``_inject_value`` for a whole-string placeholder whose
#: param is in ``omit`` — the enclosing dict/list drops the key instead of
#: sending it. Distinct from ``None`` (a legitimately injected null).
_OMIT = object()


def _inject_value(template: Any, params: dict[str, Any], omit: frozenset[str] = frozenset()) -> Any:
    """Fill placeholders in query/body/header templates.

    A whole-string placeholder (``"{n}"``) preserves the param's native type
    (int, bool, ...); placeholders embedded in text are string-substituted. A
    whole-string placeholder whose param is in ``omit`` yields :data:`_OMIT`, and
    the enclosing dict/list drops that key (used for ``omit_if_default`` params).
    """
    if isinstance(template, str):
        whole = _PLACEHOLDER.fullmatch(template)
        if whole is not None:
            return _OMIT if whole.group(1) in omit else params.get(whole.group(1))
        return _PLACEHOLDER.sub(lambda m: str(params.get(m.group(1), "")), template)
    if isinstance(template, dict):
        return {
            k: v for k, raw in template.items() if (v := _inject_value(raw, params, omit)) is not _OMIT
        }
    if isinstance(template, list):
        return [v for raw in template if (v := _inject_value(raw, params, omit)) is not _OMIT]
    return template


def _expose_to_schema(expose: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Compile the YAML ``expose`` block into the JSON ``inputSchema`` Strands wants.

    Raises:
        ValueError: If a param declares an unsupported ``type``.
    """
    properties: dict[str, Any] = {}
    required: list[str] = []
    for pname, spec in expose.items():
        ptype = spec.get("type", "string")
        if ptype not in _JSON_TYPES:
            raise ValueError(
                f"expose.{pname}.type '{ptype}' is invalid; one of {list(_JSON_TYPES)}"
            )
        prop: dict[str, Any] = {"type": ptype, "description": spec.get("description", "")}
        if "default" in spec:
            prop["default"] = spec["default"]
        if "enum" in spec:
            prop["enum"] = spec["enum"]
        properties[pname] = prop
        if spec.get("required"):
            required.append(pname)
    return {"json": {"type": "object", "properties": properties, "required": required}}


def _expose_to_signature(expose: dict[str, dict[str, Any]]) -> inspect.Signature:
    """Build a synthetic signature with one keyword param per ``expose`` entry.

    Strands derives its input-validation Pydantic model from ``inspect.signature``
    of the tool function, *not* from the explicit ``inputSchema``. A bare
    ``runner(**kwargs)`` would make it require a literal ``kwargs`` field and
    reject the real params. Attaching this signature to ``runner`` makes the
    validation model match the schema the model actually calls with.
    """
    params: list[inspect.Parameter] = []
    for pname, spec in expose.items():
        annotation: Any = _PY_TYPES.get(spec.get("type", "string"), str)
        if "default" in spec:
            default: Any = spec["default"]
        elif spec.get("required"):
            default = inspect.Parameter.empty
        else:
            default, annotation = None, annotation | None
        params.append(
            inspect.Parameter(
                pname, inspect.Parameter.KEYWORD_ONLY, annotation=annotation, default=default
            )
        )
    return inspect.Signature(params)


def _validate_domain(
    name: str,
    description: str | None,
    bind: dict[str, Any],
    expose: dict[str, dict[str, Any]],
) -> None:
    """Fail-fast validation of a domain-mode config, at agent build time.

    Raises:
        ValueError: On any inconsistency between ``bind`` and ``expose``.
    """
    if not description:
        raise ValueError(
            f"apicall '{name}': domain mode (expose) requires a 'description' "
            "(it is the tool's contract with the model)."
        )
    if not bind.get("base_url"):
        raise ValueError(f"apicall '{name}': bind.base_url is required in domain mode.")
    if not bind.get("path"):
        raise ValueError(f"apicall '{name}': bind.path is required in domain mode.")

    path_params = _find_placeholders(bind["path"])
    other_params = (
        _find_placeholders(bind.get("query"))
        | _find_placeholders(bind.get("body"))
        | _find_placeholders(bind.get("headers"))
    )
    used = path_params | other_params

    missing = used - set(expose)
    if missing:
        raise ValueError(
            f"apicall '{name}': bind references {sorted(missing)} not declared in expose."
        )

    not_required = [p for p in path_params if not expose[p].get("required")]
    if not_required:
        raise ValueError(
            f"apicall '{name}': path params {sorted(not_required)} must be 'required: true' "
            "in expose (an empty path segment yields an invalid URL)."
        )

    omit_no_default = [
        p for p, s in expose.items() if s.get("omit_if_default") and "default" not in s
    ]
    if omit_no_default:
        raise ValueError(
            f"apicall '{name}': expose params {sorted(omit_no_default)} set 'omit_if_default' "
            "without a 'default' (nothing to compare against)."
        )

    omit_path = [p for p in path_params if expose[p].get("omit_if_default")]
    if omit_path:
        raise ValueError(
            f"apicall '{name}': path params {sorted(omit_path)} cannot set 'omit_if_default' "
            "(a path segment is always required and never omitted)."
        )

    unused = set(expose) - used
    if unused:
        logger.warning(
            "apicall '%s': expose params %s are not used in any bind template.",
            name,
            sorted(unused),
        )

    select = bind.get("select")
    if select is not None:
        if not isinstance(select, list) or not all(isinstance(s, str) for s in select):
            raise ValueError(f"apicall '{name}': bind.select must be a list of strings.")
        for entry in select:
            src, sep, dst = entry.partition(":")
            if sep and src.count(".") != dst.count("."):
                raise ValueError(
                    f"apicall '{name}': select rename '{entry}' must keep the same nesting "
                    "depth on both sides of ':' (only the leaf name may change)."
                )


def _make_domain_apicall(
    *,
    name: str,
    description: str | None,
    bind: dict[str, Any],
    expose: dict[str, dict[str, Any]],
    timeout: float,
    clean_response: bool,
) -> DecoratedFunctionTool:
    """Build a domain-shaped tool: the model fills ``expose`` params, the framework
    assembles the request from the ``bind`` template."""
    _validate_domain(name, description, bind, expose)

    base = bind["base_url"].rstrip("/")
    path_tmpl = bind["path"]
    verb = str(bind.get("method", "GET")).upper()
    query_tmpl = bind.get("query")
    body_tmpl = bind.get("body")
    header_tmpl = bind.get("headers")
    select = bind.get("select")
    session = _build_session(bind.get("static_headers"))
    input_schema = _expose_to_schema(expose)
    defaults = {p: s["default"] for p, s in expose.items() if "default" in s}
    omit_if_default = [p for p, s in expose.items() if s.get("omit_if_default")]

    def runner(**kwargs: Any) -> ToolResult:
        merged = {**defaults, **kwargs}
        # Params left at their default that opted into omit_if_default: drop their
        # key from the request entirely instead of sending the default value.
        omit = frozenset(
            p for p in omit_if_default if merged.get(p) == expose[p].get("default")
        )
        try:
            url = f"{base}{_inject_path(path_tmpl, merged)}"
        except _InjectionError as exc:
            return {"status": "error", "content": [{"text": f"Invalid request: {exc}"}]}

        query = _inject_value(query_tmpl, merged, omit) if query_tmpl is not None else None
        body = (
            _inject_value(body_tmpl, merged, omit)
            if body_tmpl is not None and verb in _WRITE_METHODS
            else None
        )
        extra_headers = (
            {k: str(v) for k, v in _inject_value(header_tmpl, merged, omit).items()}
            if header_tmpl is not None
            else None
        )
        return _execute_request(
            session,
            verb,
            url,
            json_body=body,
            query=query,
            timeout=timeout,
            clean_response=clean_response,
            select=select,
            extra_headers=extra_headers,
        )

    # Strands builds its input-validation model from the function signature, so
    # give the generic runner a signature that matches the exposed params.
    runner.__signature__ = _expose_to_signature(expose)  # type: ignore[attr-defined]
    return tool(runner, name=name, description=description, inputSchema=input_schema)


# ---------------------------------------------------------------------------
# Generic mode (model chooses path) — back-compat
# ---------------------------------------------------------------------------


def _make_generic_apicall(
    *,
    name: str,
    allowed_paths: list[str],
    base_url: str | None,
    headers: dict[str, str] | None,
    timeout: float,
    clean_response: bool,
) -> DecoratedFunctionTool:
    """Build the generic HTTP tool: the model picks path/method against an allow-list."""
    if not allowed_paths:
        raise ValueError("allowed_paths must list at least one allowed path pattern")

    base = (base_url or os.getenv("BASE_URL", "")).rstrip("/")
    patterns = list(allowed_paths)
    session = _build_session(headers)

    @tool(name=name)
    def call(
        path: Annotated[str, "Request path starting with '/', e.g. '/v1/users/42'."],
        method: Annotated[str, "HTTP method: GET, POST, PUT, PATCH or DELETE."] = "GET",
        body: Annotated[dict[str, Any] | None, "JSON body for POST/PUT/PATCH requests."] = None,
        params: Annotated[
            dict[str, Any] | None, "Query-string parameters for GET requests."
        ] = None,
    ) -> ToolResult:
        """Call the configured HTTP API and return its JSON (or text) response.

        Use this to read or write data through the service this tool is bound to.
        Only paths within the tool's allow-list will succeed.
        """
        if not any(fnmatch.fnmatch(path, p) for p in patterns):
            return {
                "status": "error",
                "content": [{"text": f"Path '{path}' is not allowed. Allowed: {patterns}"}],
            }

        verb = method.upper()
        return _execute_request(
            session,
            verb,
            f"{base}{path}",
            json_body=body if verb in _WRITE_METHODS else None,
            query=params if verb == "GET" else None,
            timeout=timeout,
            clean_response=clean_response,
        )

    return call


def make_apicall(
    *,
    name: str,
    description: str | None = None,
    bind: dict[str, Any] | None = None,
    expose: dict[str, dict[str, Any]] | None = None,
    allowed_paths: list[str] | None = None,
    base_url: str | None = None,
    headers: dict[str, str] | None = None,
    timeout: float = 8.0,
    clean_response: bool = True,
) -> DecoratedFunctionTool:
    """Build an HTTP tool bound to one API, in domain or generic mode.

    The presence of ``expose`` (or ``bind``) selects **domain mode**: the model
    fills the semantic params in ``expose`` and the framework assembles the
    request from the ``bind`` template. Otherwise **generic mode** is used: the
    model picks ``path``/``method`` against ``allowed_paths``.

    Args:
        name: Strands tool name (must be unique within the agent).
        description: Tool description shown to the model. Required in domain mode.
        bind: Domain-mode request template: ``base_url``, ``path`` (with
            ``{param}`` placeholders), ``method``, optional ``query``/``body``/
            ``headers`` (also templated), ``static_headers`` (sent verbatim) and
            ``select`` (list of dotted paths to keep from the response, dropping
            the rest — keeps a huge upstream payload out of the model's context;
            a path may traverse a list and may rename its leaf as ``"src:dst"``).
        expose: Domain-mode param schema (``name -> {type, description, required,
            default, enum, omit_if_default}``) compiled into the model-facing
            ``inputSchema``. ``omit_if_default: true`` drops the param's key from
            the request entirely when its value equals ``default`` (instead of
            sending the default), mirroring a hand-written tool that builds the
            payload conditionally. Requires a ``default``; not allowed on path
            params.
        allowed_paths: Generic-mode glob allow-list, e.g. ``["/v1/*"]``.
        base_url: Generic-mode base URL. Falls back to the ``BASE_URL`` env var.
        headers: Generic-mode static headers sent on every request.
        timeout: Per-request timeout in seconds.
        clean_response: Drop empty values from the JSON response before returning.

    Returns:
        A ``DecoratedFunctionTool`` named ``name``.

    Raises:
        ValueError: On invalid config (e.g. both modes declared, empty
            ``allowed_paths``, or a ``bind``/``expose`` inconsistency).
    """
    if expose is not None or bind is not None:
        if allowed_paths is not None:
            raise ValueError(
                f"apicall '{name}': declare either domain mode (bind/expose) or generic mode "
                "(allowed_paths), not both."
            )
        return _make_domain_apicall(
            name=name,
            description=description,
            bind=bind or {},
            expose=expose or {},
            timeout=timeout,
            clean_response=clean_response,
        )

    return _make_generic_apicall(
        name=name,
        allowed_paths=allowed_paths or [],
        base_url=base_url,
        headers=headers,
        timeout=timeout,
        clean_response=clean_response,
    )
