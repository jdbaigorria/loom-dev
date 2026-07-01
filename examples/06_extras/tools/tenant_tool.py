"""Tool that reads caller context passed via native ``invocation_state``.

``invocation_state`` is the mechanism for passing infrastructure context (JWT
claims, tenant ID, roles, feature flags) from the caller into the agent's tools
without leaking it into the user-visible prompt. The backend forwards it when it
runs the agent (``agent(query, invocation_state={...})`` — or, in dev,
``run_dev(..., extras={...})``); the tool reads it from its ``ToolContext``.
"""

from strands import tool


@tool(context=True)
def get_tenant_info(tool_context) -> dict:
    """Return the current tenant and user information from the invocation state.

    Returns:
        dict with tenant_id and user_role extracted from the caller's extras.
    """
    state = tool_context.invocation_state
    jwt = state.get("jwt", {}) or {}
    return {
        "tenant_id": state.get("tenant_id", "unknown"),
        "user_role": state.get("user_role", "guest"),
        "jwt_sub": jwt.get("sub", "anonymous"),
    }
