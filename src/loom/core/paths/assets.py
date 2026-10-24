"""Static locations of Loom's bundled package assets (scaffolding templates).

Package-relative constants: they point inside the installed ``loom`` package and
do not depend on the user's project or ``loom.toml`` — unlike ``WorkspacePaths``.
"""

from pathlib import Path

# .../loom/core/paths/assets.py → parents: paths → core → loom
INTERNAL_PACKAGE_ROOT = Path(__file__).resolve().parent.parent.parent
TEMPLATES_DIR = INTERNAL_PACKAGE_ROOT / "templates"
INIT_TEMPLATES = TEMPLATES_DIR / "init"
AGENT_TEMPLATES = TEMPLATES_DIR / "new"
