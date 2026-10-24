"""Contract: every ``strands_evals`` symbol the ACL re-exports resolves."""

from loom_evals.adapters import strands_evals


def test_all_eval_symbols_resolve():
    missing = [name for name in strands_evals.__all__ if getattr(strands_evals, name) is None]
    assert missing == [], f"Unresolved strands_evals symbols (update the ACL): {missing}"
