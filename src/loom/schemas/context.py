"""
loom.schemas.context — Execution identity for a build/run.

``LoomSession`` groups the identifiers for a single execution (``user_id``,
``session_id``). It is a constructor input for :func:`loom.build` /
:func:`loom.core.builder.build_agent` and the dev executor.

The former ``LoomContext`` (a contextvar that exposed extras to tools globally)
is gone: extras now flow as Strands-native ``invocation_state``
(``agent(input, invocation_state={...})``), which tools read via
``tool_context.invocation_state``. Identity resolution (anonymous users, session
id generation) is the backend's responsibility, not Loom's.
"""

from __future__ import annotations

from pydantic import BaseModel


class LoomSession(BaseModel):
    """Execution identifiers: the user speaking and the session they belong to."""

    user_id: str
    session_id: str
    is_anonymous: bool = False
