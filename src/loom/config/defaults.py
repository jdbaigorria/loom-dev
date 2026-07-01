"""
loom.config.defaults — Built-in scalar defaults (single source of truth).

Opinionated default *values* that aren't named presets (those live in
``loom.config.profiles``). Kept here so an opinion like the default AWS region is
defined once and referenced everywhere — schemas, CLI flags, and the init wizard —
instead of being copy-pasted across the codebase.

These remain overridable at runtime through the usual config files
(``app.yml`` for region and the session backend).
"""

# Default AWS region for Bedrock and S3-backed sessions.
DEFAULT_REGION = "us-east-1"

# Default local path for the file session backend (relative to the project root).
DEFAULT_SESSION_PATH = ".loom/sessions"
