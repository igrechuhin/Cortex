"""Manager initialization groups."""

from dataclasses import dataclass


@dataclass
class ManagerGroup:
    """Group of related managers that should be initialized together."""

    name: str
    managers: list[str]
    priority: int  # 1=always, 2=frequent, 3=occasional, 4=rare

    def __str__(self) -> str:
        """Return string representation."""
        return f"{self.name} ({len(self.managers)} managers, priority {self.priority})"


# Define manager groups
MANAGER_GROUPS = [
    ManagerGroup(
        name="core",
        managers=[
            "file_system",
            "metadata_index",
            "token_counter",
            "version_manager",
            "file_watcher",
        ],
        priority=1,
    ),
    ManagerGroup(
        name="linking",
        managers=["link_parser", "transclusion_engine", "link_validator"],
        priority=2,
    ),
    ManagerGroup(
        name="validation",
        managers=["schema_validator", "duplication_detector", "quality_metrics"],
        priority=2,
    ),
    ManagerGroup(
        name="optimization",
        managers=[
            "context_optimizer",
            "relevance_scorer",
            "progressive_loader",
            "summarization_engine",
        ],
        priority=2,
    ),
    ManagerGroup(
        name="analysis",
        managers=["pattern_analyzer", "structure_analyzer", "insight_engine"],
        priority=3,
    ),
    ManagerGroup(
        name="refactoring",
        managers=[
            "refactoring_engine",
            "consolidation_detector",
            "split_recommender",
            "reorganization_planner",
        ],
        priority=3,
    ),
    ManagerGroup(
        name="execution",
        managers=[
            "refactoring_executor",
            "approval_manager",
            "rollback_manager",
            "learning_engine",
        ],
        priority=4,
    ),
    ManagerGroup(
        name="structure",
        managers=["structure_manager", "template_manager"],
        priority=4,
    ),
    ManagerGroup(
        name="rules",
        managers=["rules_manager", "synapse_manager"],
        priority=3,
    ),
]
