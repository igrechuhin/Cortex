"""Recommend tools and scripts for a task description."""

from cortex.discovery.search_interface import search_tools_and_scripts


def recommend_tools_and_scripts(
    task_description: str,
    tool_names: list[str],
    script_names: list[str],
    min_score: float = 0.2,
    max_results: int = 15,
) -> list[tuple[str, str, float]]:
    """Recommend tools and scripts for a task description.

    Uses the same keyword search as search_tools_and_scripts;
    task_description is treated as the search query.

    Args:
        task_description: Description of the task (e.g. "format Python files").
        tool_names: Known MCP tool names.
        script_names: Known Synapse script names.
        min_score: Minimum relevance score.
        max_results: Maximum recommendations.

    Returns:
        List of (name, type, score) sorted by score descending.
    """
    return search_tools_and_scripts(
        query=task_description,
        tool_names=tool_names,
        script_names=script_names,
        min_score=min_score,
        max_results=max_results,
    )
