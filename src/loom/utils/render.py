"""Template rendering and project scaffolding utilities.

Provides Jinja2-based template rendering for scaffolding new projects and agents.
Handles conditional path generation, template variable interpolation, and file copying.

Key Features:

- **Jinja2 Environment Setup**: Pre-configured with strict undefined and whitespace control
- **Path Template Rendering**: Supports conditional path generation (e.g., skip dirs based on flags)
- **File Templating**: Processes .j2 files with variable interpolation, copies static files
- **Suffix Stripping**: Automatically removes .j2 extensions from output paths

Usage:

    from loom.utils.render import apply_template

    apply_template(
        template_root=Path("templates/new_agent"),
        output_root=Path("warp/agents"),
        context={"agent_name": "my_agent", "model": "claude-3-5-sonnet"}
    )
"""

import shutil
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined


def build_env(template_root: Path) -> Environment:
    """Create and configure a Jinja2 environment for template rendering.

    Sets up a pre-configured Jinja2 environment with:
    - Strict undefined mode (raises error if variables not in context)
    - Whitespace control (trim blocks and left-strip blocks enabled)
    - Preserved newlines at end of files

    Args:
        template_root: Directory containing Jinja2 template files.

    Returns:
        Environment: Configured Jinja2 environment ready for rendering.
    """
    return Environment(
        loader=FileSystemLoader(template_root),
        undefined=StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
        keep_trailing_newline=True,
    )


def render_path(env: Environment, rel_path: Path, context: dict) -> Path | None:
    """Render a file path template with context variables and conditional logic.

    Processes path templates with Jinja2 to support:
    - Variable substitution: {{% raw %}}{{ variable_name }}{{% endraw %}}
    - Conditional segments: {{% raw %}}{% if condition %}path_segment{% endif %}{{% endraw %}}
    - Automatic .j2 suffix removal from path components

    If any path segment evaluates to empty (from conditional blocks),
    returns None to skip this path entirely.

    Args:
        env: Jinja2 environment (from build_env()).
        rel_path: Relative path with Jinja2 template syntax.
        context: Variables to interpolate in path template.

    Returns:
        Path | None: Rendered path with .j2 extensions stripped from parts,
            or None if any segment is empty (conditional exclusion).

    Example:
        >>> env = build_env(Path("templates"))
        >>> ctx = {"agent_name": "my_agent"}
        >>> path = render_path(env, Path("agents/{{ agent_name }}"), ctx)
        >>> print(path)
        agents/my_agent
    """
    rendered = env.from_string(rel_path.as_posix()).render(**context)
    # If any segment is empty (from a false {% if %} block), skip this path
    if any(seg == "" for seg in rendered.split("/")):
        return None
    # Strip .j2 suffix from every path part (dirnames and filename)
    parts = [p[:-3] if p.endswith(".j2") else p for p in Path(rendered).parts]
    return Path(*parts) if parts else Path(rendered)


def apply_template(
    template_root: Path, output_root: Path, context: dict | None = None, force: bool = False
) -> list[Path]:
    """Apply a Jinja2 template directory to generate scaffolded project structure.

    Recursively processes a template directory:
    1. Creates output directories (with path rendering)
    2. Renders Jinja2 templates (.j2 files) with context variables
    3. Copies static files as-is

    Skips any paths that render to empty segments (from conditional logic).
    Raises error if output directory exists and is not empty (unless force=True).

    Args:
        template_root: Root directory containing template files and directories.
        output_root: Destination root for rendered output.
        context: Variable context for Jinja2 rendering (default: {}).
            Common variables: agent_name, model, description, etc.
        force: If True, overwrite existing non-empty directories.
            If False, raises FileExistsError if output exists and not empty.

    Returns:
        list[Path]: Paths of all rendered files and created directories.

    Raises:
        FileExistsError: If output directory exists, is not empty, and force=False.
        jinja2.exceptions.UndefinedError: If template references undefined variables
            (due to StrictUndefined mode).

    Example:
        Scaffold a new agent using a template::

            files = apply_template(
                template_root=Path("loom/templates/new/agent"),
                output_root=Path("warp/agents"),
                context={
                    "agent_name": "quality_checker",
                    "model": "claude-opus-4-1",
                    "description": "Checks output quality"
                }
            )
            print(f"Created {len(files)} files")
    """

    context = context or {}
    env = build_env(template_root)

    if context and "folder_name" in context:
        folder_name = context.get("folder_name", "")
        folder_out_dir = output_root / folder_name

        if folder_out_dir.exists() and any(folder_out_dir.rglob("*")) and not force:
            raise FileExistsError(
                f"Folder directory {folder_out_dir} already exists and is not empty."
            )

    files_to_render: list[Path] = []
    for d in [p for p in template_root.rglob("*") if p.is_dir()]:
        rel = d.relative_to(template_root)
        out_rel = render_path(env, rel, context)
        if out_rel is None:
            continue
        out_path = output_root / out_rel
        out_path.mkdir(parents=True, exist_ok=True)
        files_to_render.append(out_path)

    for src in [p for p in template_root.rglob("*") if p.is_file()]:
        rel = src.relative_to(template_root)

        out_rel = render_path(env, rel, context)
        if out_rel is None:
            continue
        out_path = output_root / out_rel

        if rel.suffix == ".j2":
            tpl = env.get_template(rel.as_posix())
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(tpl.render(**context), encoding="utf-8")
        else:
            out_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, out_path)

        files_to_render.append(out_path)

    return files_to_render
