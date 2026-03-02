"""Registry of known MCP tools and Synapse scripts for discovery."""

from pathlib import Path

from cortex.core.path_resolver import CortexResourceType, get_cortex_path

# Canonical MCP tool names for discovery (keep in sync with docs/api/tools.md).
_KNOWN_TOOL_NAMES: list[str] = [
    "analyze",
    "analyze_health_check",
    "analyze_project_summary",
    "analyze_structure",
    "analyze_usage_patterns",
    "apply_refactoring",
    "approve_refactoring",
    "capture_session_script",
    "check_duplications",
    "check_migration_status",
    "check_structure_health",
    "cleanup_metadata_index",
    "cleanup_project_structure",
    "configure",
    "configure_learning",
    "configure_optimization",
    "configure_validation",
    "execute_pre_commit_checks",
    "fix_markdown_lint",
    "fix_roadmap_corruption",
    "generate_memory_bank_template",
    "query_memory_bank",
    "get_memory_bank_structure",
    "get_optimization_insights",
    "get_relevance_scores",
    "get_refactoring_history",
    "get_structure_info",
    "get_file_metadata",
    "initialize_memory_bank",
    "list_session_scripts",
    "load_context",
    "manage_session_scripts",
    "manage_file",
    "migrate_memory_bank",
    "migrate_project_structure",
    "provide_feedback",
    "query_usage",
    "rollback_refactoring",
    "rules",
    "session",
    "setup_cursor_integration",
    "setup_project_structure",
    "setup_shared_rules",
    "summarize_content",
    "suggest_consolidation",
    "suggest_file_splits",
    "suggest_reorganization",
    "sync_shared_rules",
    "update_shared_rule",
    "get_relevant_rules",
    "index_rules",
    "validate",
    "check_token_budget",
    "get_quality_score",
    "preview_refactoring",
    "check_mcp_connection_health",
    "skill_pack",
    "cache_json",
    "synapse",
    "run_composite_workflow",
]


def get_known_tool_names() -> list[str]:
    """Return list of known MCP tool names for discovery and gap analysis."""
    return list(_KNOWN_TOOL_NAMES)


def get_known_script_names(project_root: Path) -> list[str]:
    """List Synapse script names (file stems) from .cortex/synapse/scripts/python."""
    synapse_root = get_cortex_path(project_root, CortexResourceType.SYNAPSE)
    scripts_dir = synapse_root / "scripts" / "python"
    if not scripts_dir.exists():
        return []
    stems: list[str] = []
    for path in sorted(scripts_dir.glob("*.py")):
        if path.name.startswith("_"):
            continue
        stems.append(path.stem)
    return stems
