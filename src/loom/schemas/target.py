"""loom.schemas.target — Discovery types: what a buildable target *is*.

The catalog contract between Loom and its caller (backend/harness): a target has
a ``name``, a ``kind``, and a human ``description``. ``kind`` tells the caller
which runtime shape to mount — an ``agent`` (``strands.Agent``), a ``workflow``
(``Graph``/``Swarm``), or a ``bidi`` agent (experimental full-duplex). It is a
property *reported by the* :class:`~loom.ports.ConfigSource`, not inferred from
the filesystem at the call site.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Literal

from loom.schemas.config.labels import LabelValue

TargetKind = Literal["agent", "workflow", "bidi"]


@dataclass(frozen=True)
class TargetInfo:
    """A buildable target as surfaced by discovery.

    ``labels`` are the product-owned labels of the target's *effective* config
    (``app.yml`` ``defaults`` applied). Loom reports them and never interprets
    them. They are read-only: list values are tuples.
    """

    name: str
    kind: TargetKind
    description: str = ""
    labels: Mapping[str, LabelValue] = field(default_factory=dict, hash=False)

    def __post_init__(self) -> None:
        frozen = {k: tuple(v) if isinstance(v, list) else v for k, v in dict(self.labels).items()}
        object.__setattr__(self, "labels", MappingProxyType(frozen))
