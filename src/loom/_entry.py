"""Console-script entry point with a friendly guard for the ``cli`` extra.

The runtime core (``pip install loom-declarative``) ships without Typer and the
rest of the authoring stack. If someone installs the slim core and still runs
``loom ...``, importing the CLI raises ``ImportError``; we turn that into a clear
instruction instead of a stack trace.
"""

from __future__ import annotations

import sys

_MISSING_CLI_HINT = (
    "The Loom CLI requires the 'cli' extra, which is not installed.\n"
    "Install it with:\n\n"
    "    pip install 'loom-declarative[cli]'\n"
)


def main() -> None:
    """Launch the Typer app, or explain how to install the CLI extra."""
    try:
        from loom.cli.cli import app
    except ImportError as exc:
        # Only swallow the CLI-stack import failure; re-raise anything unexpected.
        missing = getattr(exc, "name", "") or ""
        if missing in {"typer", "inquirerpy", "InquirerPy", "jinja2", "rich"}:
            print(_MISSING_CLI_HINT, file=sys.stderr)
            raise SystemExit(1) from exc
        raise
    app()
