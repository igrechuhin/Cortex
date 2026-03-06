"""
Default optimization configuration structure.

This module holds the canonical default dict for optimization.json.
tool_search is injected at load time in config_loading to avoid circular imports.
"""

from cortex.core.constants import MemoryBankFile
from cortex.core.path_resolver import CortexResourceType

DEFAULT_OPTIMIZATION_CONFIG: dict[str, object] = {
    "enabled": True,
    "token_budget": {
        "default_budget": 80000,
        "max_budget": 100000,
        "reserve_for_response": 10000,
    },
    "loading_strategy": {
        "default": "dependency_aware",
        "mandatory_files": [MemoryBankFile.PROJECT_BRIEF],
        "priority_order": [
            MemoryBankFile.PROJECT_BRIEF,
            MemoryBankFile.ACTIVE_CONTEXT,
            MemoryBankFile.SYSTEM_PATTERNS,
            MemoryBankFile.TECH_CONTEXT,
            MemoryBankFile.PRODUCT_CONTEXT,
            MemoryBankFile.PROGRESS,
        ],
        "always_load_sections": {
            MemoryBankFile.PROJECT_BRIEF: [],
            MemoryBankFile.ACTIVE_CONTEXT: ["## Current Focus", "## Next Steps"],
        },
    },
    "summarization": {
        "enabled": True,
        "auto_summarize_old_files": False,
        "age_threshold_days": 90,
        "target_reduction": 0.5,
        "strategy": "extract_key_sections",
        "cache_summaries": True,
    },
    "relevance": {
        "keyword_weight": 0.4,
        "dependency_weight": 0.3,
        "recency_weight": 0.2,
        "quality_weight": 0.1,
    },
    "performance": {
        "cache_enabled": True,
        "cache_ttl_seconds": 3600,
        "max_cache_size_mb": 50,
    },
    "rules": {
        "enabled": False,
        "rules_folder": ".cursorrules",
        "reindex_interval_minutes": 30,
        "auto_include_in_context": True,
        "max_rules_tokens": 5000,
        "min_relevance_score": 0.3,
        "rule_priority": "local_overrides_shared",
        "context_aware_loading": True,
        "always_include_generic": True,
        "context_detection": {
            "enabled": True,
            "detect_from_task": True,
            "detect_from_files": True,
            "language_keywords": {
                "python": ["python", "django", "flask", "fastapi", "pytest", "py"],
                "swift": ["swift", "swiftui", "ios", "uikit", "combine", "cocoa"],
                "javascript": [
                    "javascript",
                    "js",
                    "react",
                    "vue",
                    "node",
                    "typescript",
                    "ts",
                ],
                "rust": ["rust", "cargo", "rustc"],
                "go": ["golang", "go"],
                "java": ["java", "spring", "maven", "gradle"],
                "csharp": ["c#", "csharp", "dotnet", ".net"],
                "cpp": ["c++", "cpp", "cmake"],
            },
        },
    },
    "synapse": {
        "enabled": False,
        "synapse_folder": f".cortex/{CortexResourceType.SYNAPSE.value}",
        "synapse_repo": "",
        "auto_sync": True,
        "sync_interval_minutes": 60,
    },
    "self_evolution": {
        "enabled": True,
        "analysis": {
            "track_usage_patterns": True,
            "pattern_window_days": 30,
            "min_access_count": 5,
            "track_task_patterns": True,
        },
        "insights": {
            "auto_generate": False,
            "min_impact_score": 0.5,
            "categories": [
                "usage",
                "organization",
                "redundancy",
                "dependencies",
                "quality",
            ],
        },
    },
}
