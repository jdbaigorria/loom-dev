"""loom.schemas.target — Discovery types: what a buildable target *is*.

The catalog contract between Loom and its caller (backend/harness): a target has
a ``name``, a ``kind``, and a human ``description``. ``kind`` tells the caller
which runtime shape to mount — an ``agent`` (``strands.Agent``), a ``workflow``
(``Graph``/``Swarm``), or a ``bidi`` agent (experimental full-duplex). It is a
property *reported by the* :class:`~loom.ports.ConfigSource`, not inferred from
the filesystem at the call site.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

TargetKind = Literal["agent", "workflow", "bidi"]


@dataclass(frozen=True)
class TargetInfo:
    """A buildable target as surfaced by discovery."""

    name: str
    kind: TargetKind
    description: str = ""
