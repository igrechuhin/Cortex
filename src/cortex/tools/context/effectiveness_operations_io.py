"""
Context Analysis Operations - I/O

File and statistics I/O for context analysis.
"""

import json
from datetime import datetime
from pathlib import Path

from cortex.core.path_resolver import CortexResourceType, get_cortex_path
from cortex.core.synapse_usage_config import is_usage_writable
from cortex.tools.context.effectiveness_models import (
    ContextInsights,
    ContextUsageStatistics,
)


def _project_root_from_context_statistics_path(stats_path: Path) -> Path | None:
    """Infer repo root from `.cortex/.session/context-usage-statistics.json`."""
    resolved = stats_path.resolve()
    session_dir = resolved.parent
    if session_dir.name != ".session":
        return None
    cortex_dir = session_dir.parent
    if cortex_dir.name != ".cortex":
        return None
    return cortex_dir.parent


def get_statistics_path(project_root: Path) -> Path:
    """Get path to context usage statistics file."""
    session_dir = get_cortex_path(project_root, CortexResourceType.SESSION)
    return session_dir / "context-usage-statistics.json"


def load_statistics(stats_path: Path) -> ContextUsageStatistics:
    """Load existing statistics or create empty structure."""
    if stats_path.exists():
        with open(stats_path, encoding="utf-8") as f:
            data = json.load(f)
        stats = ContextUsageStatistics.model_validate(data)
        from cortex.tools.context.effectiveness_operations import (
            reconcile_context_usage_statistics_entries,
        )

        if reconcile_context_usage_statistics_entries(stats):
            project_root = _project_root_from_context_statistics_path(stats_path)
            if project_root is not None and is_usage_writable(project_root):
                save_statistics(stats_path, stats)
        return stats

    return ContextUsageStatistics(
        last_updated=datetime.now().isoformat(timespec="minutes"),
        total_sessions_analyzed=0,
        total_load_context_calls=0,
        avg_token_utilization=0.0,
        avg_files_selected=0.0,
        avg_relevance_score=0.0,
        common_task_patterns={},
        insights=create_empty_insights(),
        entries=[],
    )


def create_empty_insights() -> ContextInsights:
    """Create empty insights structure."""
    return ContextInsights(
        task_type_recommendations={},
        file_effectiveness={},
        learned_patterns=[],
        budget_recommendations={},
        role_recommendations={},
        role_budget_recommendations={},
    )


def save_statistics(stats_path: Path, stats: ContextUsageStatistics) -> None:
    """Save statistics to file."""
    stats_path.parent.mkdir(parents=True, exist_ok=True)
    with open(stats_path, "w", encoding="utf-8") as f:
        json.dump(stats.model_dump(mode="json"), f, indent=2)
