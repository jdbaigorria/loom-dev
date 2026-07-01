"""
loom.hooks — Built-in hook implementations para LOOM.

Cada hook es un ``HookProvider`` de Strands listo para declararse en el YAML
del agente bajo la sección ``hooks:``.

Built-ins disponibles:
- ``logging``     → ``LoggingHook``      — loguea inicio/fin de cada invocación.
- ``tool_tracker`` → ``ToolTrackerHook`` — loguea cada tool call con nombre y resultado.
- ``rate_limit``  → ``RateLimitHook``    — cancela tool calls cuando se supera el límite.
"""
