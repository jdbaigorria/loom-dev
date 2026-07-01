"""Resilient symbol resolution for the Strands SDK.

Strands moves classes between module paths across releases (e.g.
``strands.models.bedrock.BedrockModel`` may also be reachable as
``strands.models.BedrockModel``). Instead of pinning a single deep import path
that breaks on the next release, :func:`resolve` accepts an ordered list of
candidate paths and returns the first one that imports successfully.

When *every* candidate fails, a :class:`LoomStrandsCompatError` is raised with the
full list of attempted paths — an actionable signal that this file (and only this
file) needs updating for the installed Strands version.
"""

from __future__ import annotations

import importlib
from typing import Any


class LoomStrandsCompatError(ImportError):
    """A Strands symbol Loom depends on could not be resolved.

    Raised by :func:`resolve` when none of the candidate import paths succeed.
    Indicates the installed Strands version moved or removed a symbol; the fix
    is to add the new path to the relevant ``resolve(...)`` call in
    ``loom.adapters.strands``.
    """

    def __init__(self, paths: tuple[str, ...], last_error: Exception | None = None) -> None:
        self.paths = paths
        self.last_error = last_error
        joined = "\n  - ".join(paths)
        super().__init__(
            "Loom could not resolve a required Strands symbol. None of these "
            f"import paths worked:\n  - {joined}\n"
            "The installed Strands version likely moved it. Update the matching "
            "resolve(...) call in loom/adapters/strands/."
            + (f"\nLast error: {last_error!r}" if last_error else "")
        )


def resolve(*paths: str, optional: bool = False) -> Any:
    """Return the first importable symbol among ``paths``.

    Args:
        *paths: Ordered ``"module.path.Symbol"`` candidates, most-preferred first.
        optional: If ``True``, return ``None`` instead of raising when every
            candidate fails (e.g. an optional provider whose extra is not
            installed).

    Returns:
        The resolved attribute, or ``None`` when ``optional`` and unresolved.

    Raises:
        LoomStrandsCompatError: If no candidate resolves and ``optional`` is False.
    """
    last_error: Exception | None = None
    for path in paths:
        module_name, _, attr = path.rpartition(".")
        if not module_name:
            continue
        try:
            module = importlib.import_module(module_name)
            return getattr(module, attr)
        except AttributeError as exc:
            # The final segment may be a submodule not yet imported as an
            # attribute (e.g. ``pkg.subpkg.module``). Mirror ``from x import y``
            # semantics by importing the full path as a module.
            last_error = exc
            try:
                return importlib.import_module(path)
            except ImportError as sub_exc:
                last_error = sub_exc
                continue
        except ImportError as exc:
            last_error = exc
            continue

    if optional:
        return None
    raise LoomStrandsCompatError(paths, last_error)


def is_available(*paths: str) -> bool:
    """Return ``True`` if any of ``paths`` resolves (for feature detection)."""
    return resolve(*paths, optional=True) is not None
