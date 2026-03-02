"""Helper functions for Memory Bank statistics.

Extracted from foundation_stats to keep that file under 400 lines.
"""

from pathlib import Path
from typing import cast

from cortex.core.models import JsonValue, ModelDict, ResponseFormat
from cortex.tools.session_models import TokenBudgetStatus


def sum_file_field(files_metadata: dict[str, ModelDict], field_name: str) -> int:
    """Sum a numeric field across all files metadata."""
    total = 0
    for file_data in files_metadata.values():
        value = file_data.get(field_name, 0)
        if isinstance(value, int):
            total += value
        elif isinstance(value, float):
            total += int(value)
    return total


def extract_last_updated(index_stats: ModelDict) -> str | None:
    """Extract last_full_scan timestamp from index stats."""
    totals_raw = index_stats.get("totals")
    if not isinstance(totals_raw, dict):
        return None
    last_full_scan = totals_raw.get("last_full_scan")
    return last_full_scan if isinstance(last_full_scan, str) else None


def build_summary_dict(
    files_metadata: dict[str, ModelDict],
    total_tokens: int,
    total_size: int,
    total_reads: int,
    history_size: int,
) -> ModelDict:
    """Build summary model with calculated totals."""
    return {
        "total_files": len(files_metadata),
        "total_tokens": total_tokens,
        "total_size_bytes": total_size,
        "total_size_kb": round(total_size / 1024, 2),
        "total_reads": total_reads,
        "history_size_bytes": history_size,
        "history_size_kb": round(history_size / 1024, 2),
    }


def calculate_token_status(
    total_tokens: int, max_tokens: int, warn_threshold: float
) -> TokenBudgetStatus:
    """Calculate token budget status based on usage."""
    warn_threshold_tokens = int(max_tokens * (warn_threshold / 100))
    if total_tokens >= max_tokens:
        return TokenBudgetStatus.OVER_BUDGET
    if total_tokens >= warn_threshold_tokens:
        return TokenBudgetStatus.WARNING
    return TokenBudgetStatus.HEALTHY


def calculate_totals(
    files_metadata: dict[str, ModelDict],
) -> tuple[int, int, int]:
    """Calculate totals for tokens, size, and reads.

    Returns:
        Tuple of (total_tokens, total_size, total_reads)
    """
    total_tokens = sum_file_field(files_metadata, "token_count")
    total_size = sum_file_field(files_metadata, "size_bytes")
    total_reads = sum_file_field(files_metadata, "read_count")
    return total_tokens, total_size, total_reads


def build_base_stats_result(
    root: Path,
    files_metadata: dict[str, ModelDict],
    totals: tuple[int, int, int],
    history_size: int,
    index_stats: ModelDict,
) -> ModelDict:
    """Build base statistics result model."""
    total_tokens, total_size, total_reads = totals
    summary = build_summary_dict(
        files_metadata, total_tokens, total_size, total_reads, history_size
    )
    last_updated = extract_last_updated(index_stats)

    files_payload: dict[str, JsonValue] = {
        file_name: cast(JsonValue, meta) for file_name, meta in files_metadata.items()
    }
    return {
        "status": "success",
        "project_root": str(root),
        "summary": summary,
        "last_updated": last_updated,
        "index_stats": index_stats,
        "files": files_payload,
    }


def format_memory_bank_stats_response(
    result_dict: ModelDict, response_format: ResponseFormat
) -> str:
    """Format get_memory_bank_stats response based on response_format."""
    import json

    if response_format == ResponseFormat.CONCISE:
        summary_raw: JsonValue | None = result_dict.get("summary")
        summary: ModelDict = summary_raw if isinstance(summary_raw, dict) else {}
        token_budget_raw: JsonValue | None = result_dict.get("token_budget")
        token_budget: ModelDict = (
            token_budget_raw if isinstance(token_budget_raw, dict) else {}
        )
        concise_payload: dict[str, JsonValue] = {
            "status": result_dict.get("status", "success"),
            "total_files": summary.get("total_files"),
            "total_tokens": summary.get("total_tokens"),
            "usage_percentage": token_budget.get("usage_percentage"),
        }
        return json.dumps(concise_payload, indent=2)
    return json.dumps(result_dict, indent=2)
