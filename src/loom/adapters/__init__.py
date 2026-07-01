"""loom.adapters — Anti-corruption layer between Loom and external SDKs.

Subpackages here are the **only** place in Loom allowed to import third-party
agent runtimes (currently ``strands`` and ``strands_evals``). The rest of the
codebase imports the symbols it needs from ``loom.adapters.strands`` instead of
reaching into the vendor packages directly.

Rationale: Strands reorganizes its internal module paths frequently between
releases. Centralizing every import in one layer means a breaking upstream
release is fixed in a single file (``loom/adapters/strands/_resolve.py`` plus the
re-export modules) instead of being scattered across a dozen loaders.
"""
