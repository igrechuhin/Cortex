"""
Context Analysis Operations - I/O

File and statistics I/O for context analysis.
"""

import json
from datetime import datetime
from pathlib import Path

from cortex.core.path_resolver import CortexResourceType, get_cortex_path
from cortex.tools.models import ContextInsights, ContextUsageStatistics


def get_statistics_path(project_root: Path) -> Path:
    """Get path to context usage statistics file."""
    session_dir = get_cortex_path(project_root, CortexResourceType.SESSION)
    return session_dir / "context-usage-statistics.json"


def load_statistics(stats_path: Path) -> ContextUsageStatistics:
    """Load existing statistics or create empty structure."""
    if stats_path.exists():
        with open(stats_path, encoding="utf-8") as f:
            data = json.load(f)
            return ContextUsageStatistics.model_validate(data)

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
