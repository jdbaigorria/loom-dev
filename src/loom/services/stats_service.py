"""
loom.services.stats_service — Carga y agregación de métricas de agentes.

Lee los archivos JSONL generados por ``loom.core.response.save_invocation`` (vía
el ejecutor dev ``run_dev``) y produce un resumen agregado para mostrar con
``loom agent stats <name>``.
"""

import json
import logging
from collections import Counter
from pathlib import Path

logger = logging.getLogger(__name__)


def load_stats(stats_file: Path) -> list[dict]:
    """Lee el JSONL de stats y retorna lista de registros.

    Args:
        stats_file: Path al archivo ``.loom/stats/{name}.jsonl``.

    Returns:
        Lista de dicts con los registros. Lista vacía si el archivo no existe
        o está vacío. Las líneas con JSON inválido se omiten con un warning.
    """
    if not stats_file.exists():
        return []

    records = []
    for line in stats_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            logger.warning("Skipping malformed stats line in '%s'", stats_file)

    return records


def _usage(record: dict) -> tuple[int, int, int]:
    """(input, output, total) tokens — from the Strands summary, with legacy fallback."""
    usage = (record.get("metrics") or {}).get("accumulated_usage") or {}
    return (
        usage.get("inputTokens", record.get("input_tokens", 0)),
        usage.get("outputTokens", record.get("output_tokens", 0)),
        usage.get("totalTokens", record.get("total_tokens", 0)),
    )


def _latency(record: dict) -> float:
    """Invocation duration — from the Strands summary, with legacy fallback."""
    metrics = record.get("metrics") or {}
    return float(metrics.get("total_duration", record.get("response_time_ms", 0.0)))


def _tool_names(record: dict) -> list[str]:
    """Tool names used — from the summary's tool_usage, with legacy fallback."""
    tool_usage = (record.get("metrics") or {}).get("tool_usage")
    if isinstance(tool_usage, dict):
        return list(tool_usage.keys())
    return list(record.get("tool_calls", []))


def aggregate(records: list[dict]) -> dict:
    """Aggregate metrics from a list of invocation records.

    Reads from each record's Strands ``metrics`` summary (falling back to the
    legacy flat fields for records written before that change).

    Args:
        records: List of dicts as returned by ``load_stats()``.

    Returns:
        Dict with aggregated metrics. If ``records`` is empty, returns
        ``{"invocations": 0}`` with no other fields.
    """
    n = len(records)
    if n == 0:
        return {"invocations": 0}

    usages = [_usage(r) for r in records]
    total_input = sum(u[0] for u in usages)
    total_output = sum(u[1] for u in usages)
    total_tokens = sum(u[2] for u in usages)
    total_latency = sum(_latency(r) for r in records)

    tool_counter: Counter = Counter()
    for r in records:
        for tool in _tool_names(r):
            tool_counter[tool] += 1

    last_record = max(records, key=lambda r: r.get("ts", ""))
    system_prompt_tokens = last_record.get("system_prompt_tokens", 0)

    return {
        "invocations": n,
        "last_invocation": last_record.get("ts"),
        "total_input_tokens": total_input,
        "total_output_tokens": total_output,
        "total_tokens": total_tokens,
        "avg_input_tokens": round(total_input / n),
        "avg_output_tokens": round(total_output / n),
        "avg_response_time_ms": round(total_latency / n, 1),
        "system_prompt_tokens": system_prompt_tokens,
        "top_tools": tool_counter.most_common(5),
    }
