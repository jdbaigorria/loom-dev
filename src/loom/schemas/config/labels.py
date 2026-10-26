"""Catalog labels: flat, product-owned metadata attached to an agent or workflow.

Loom carries labels but never interprets them. Selection (``by_label``) belongs to
the harness; the meaning of each key belongs to the product. The ``loom.`` key
prefix is reserved for Loom's own future use.
"""

from typing import Annotated

from pydantic import StringConstraints

LabelKey = Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)*$")]
LabelScalar = str | int | float | bool
LabelValue = LabelScalar | list[LabelScalar]
