"""
Rules management for custom project rules integration.

This module provides functionality to manage custom rules from a specified
folder (e.g., .cortex/rules, .ai-rules) and make them available for
context optimization and relevance scoring. It delegates indexing operations
to RulesIndexer, hybrid resolution to RulesHybridMixin, and scoring /
budget selection to RulesScoringMixin.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import cast

from cortex.core.file_system import FileSystemManager
from cortex.core.metadata_index import MetadataIndex
from cortex.core.models import ModelDict, OperationStatus
from cortex.core.token_counter import TokenCounter
from cortex.rules.synapse_manager import SynapseManager

from .models import (
    DetectedContextModel,
    IndexedRuleModel,
    OptimizationRuleCategory,
    RuleSectionModel,
    RulesManagerStatusModel,
    RulesResultModel,
    ScoredRuleModel,
)
from .rules_hybrid import RulesHybridMixin
from .rules_indexer import RulesIndexer
from .rules_scoring import RulesScoringMixin

logger = logging.getLogger(__name__)


class RulesManager(RulesScoringMixin, RulesHybridMixin):
    """
    Manage custom rules from project folders.

    Enhanced to support both local rules and Synapse rules from git submodules.
    Delegates indexing operations to RulesIndexer.
    """

    indexer: RulesIndexer

    def __init__(
        self,
        project_root: Path,
        file_system: FileSystemManager,
        metadata_index: MetadataIndex,
        token_counter: TokenCounter,
        rules_folder: str | None = None,
        reindex_interval_minutes: int = 30,
        synapse_manager: SynapseManager | None = None,
    ):
        """
        Initialize rules manager.

        Args:
            project_root: Project root directory
            file_system: File system manager
            metadata_index: Metadata index
            token_counter: Token counter
            rules_folder: Optional custom rules folder path
            reindex_interval_minutes: Reindex interval in minutes
            synapse_manager: Optional Synapse manager for cross-project rules
        """
        self.project_root: Path = Path(project_root)
        self.file_system: FileSystemManager = file_system
        self.metadata_index: MetadataIndex = metadata_index
        self.token_counter = token_counter
        self.rules_folder: str | None = rules_folder
        self.synapse_manager = synapse_manager

        self.indexer = RulesIndexer(
            project_root=project_root,
            token_counter=token_counter,
            reindex_interval_minutes=reindex_interval_minutes,
        )
        self._initialized: bool = False
        self._validate_dependencies()

    def _validate_dependencies(self) -> None:
        """Validate required dependencies have the expected API.

        Uses duck-type checks (hasattr) so mocks work in tests while
        still catching misconfiguration at construction time.
        """
        if not hasattr(self.token_counter, "count_tokens"):
            raise TypeError(
                f"token_counter must provide count_tokens(); got {type(self.token_counter).__name__}"
            )
        if not hasattr(self.indexer, "get_index"):
            raise TypeError(
                f"indexer must provide get_index(); got {type(self.indexer).__name__}"
            )

    # ---- lifecycle ----------------------------------------------------------

    async def initialize(self) -> ModelDict:
        """
        Initialize rules manager and perform initial indexing.

        Idempotent: safe to call multiple times.
        """
        if self._initialized:
            return {"status": "ok", "message": "Already initialized"}
        if not self.rules_folder:
            message = "No rules folder configured"
            return {"status": "disabled", "message": message}

        rules_path = self.project_root / self.rules_folder
        if not rules_path.exists():
            message = f"Rules folder not found: {self.rules_folder}"
            return {"status": "not_found", "message": message}

        result = await self.index_rules()
        await self.indexer.start_auto_reindex(self.rules_folder)
        self._initialized = True
        return result

    async def index_rules(self, force: bool = False) -> ModelDict:
        """
        Index all rules files from the configured folder.

        Delegates to RulesIndexer.
        """
        if not self.rules_folder:
            error = "No rules folder configured"
            return {
                "status": OperationStatus.ERROR.value,
                "error": error,
                "message": error,
            }
        return await self.indexer.index_rules(self.rules_folder, force)

    # ---- retrieval ----------------------------------------------------------

    async def get_relevant_rules(
        self,
        task_description: str,
        max_tokens: int = 5000,
        min_relevance_score: float = 0.3,
        project_files: list[Path] | None = None,
        rule_priority: str = "local_overrides_shared",
        context_aware: bool = True,
    ) -> ModelDict:
        """
        Get rules relevant to a task description.

        Enhanced to support both local and shared rules with context
        detection.

        Args:
            task_description: Description of the task
            max_tokens: Maximum tokens to include
            min_relevance_score: Minimum relevance score to include
            project_files: Optional project files for context detection
            rule_priority: Priority strategy
            context_aware: Enable intelligent context detection

        Returns:
            RulesResultModel as dict with categorized rules
        """
        result = self._initialize_result_structure()

        if self.synapse_manager and context_aware:
            model = await self._get_hybrid_rules(
                result,
                task_description,
                max_tokens,
                min_relevance_score,
                project_files,
                rule_priority,
            )
            return cast(ModelDict, model.model_dump(mode="json"))
        else:
            model = await self._get_local_only_rules(
                result, task_description, max_tokens, min_relevance_score
            )
            return cast(ModelDict, model.model_dump(mode="json"))

    def _initialize_result_structure(self) -> RulesResultModel:
        """Initialize result structure with default values."""
        return RulesResultModel(
            generic_rules=[],
            language_rules=[],
            local_rules=[],
            total_tokens=0,
            context=DetectedContextModel(),
            source="local_only",
        )

    async def _get_local_only_rules(
        self,
        result: RulesResultModel,
        task_description: str,
        max_tokens: int,
        min_relevance_score: float,
    ) -> RulesResultModel:
        """Get rules using local-only (legacy) approach."""
        local_rules = self._get_local_rules_models(
            task_description, min_relevance_score
        )

        selected_rules: list[ScoredRuleModel] = []
        total_tokens = 0

        for rule in local_rules:
            rule_tokens = rule.tokens
            if total_tokens + rule_tokens <= max_tokens:
                selected_rules.append(rule)
                total_tokens += rule_tokens
            else:
                break

        result.local_rules = selected_rules
        result.total_tokens = total_tokens
        result.source = "local_only"
        return result

    async def get_local_rules(
        self, task_description: str, min_relevance_score: float = 0.3
    ) -> list[ModelDict]:
        """
        Get local rules with relevance scoring.

        Args:
            task_description: Task description
            min_relevance_score: Minimum relevance score

        Returns:
            List of scored local rules
        """
        scored_rules = self._get_local_rules_models(
            task_description, min_relevance_score
        )
        return [cast(ModelDict, r.model_dump(mode="json")) for r in scored_rules]

    async def get_all_rules(self) -> dict[str, IndexedRuleModel]:
        """
        Get all indexed rules.

        Returns:
            Dictionary mapping file keys to indexed rule models
        """
        return self.indexer.get_index()

    # ---- local rule scoring -------------------------------------------------

    def _create_scored_rule(
        self, file_key: str, indexed_rule: IndexedRuleModel, score: float
    ) -> ScoredRuleModel:
        """Create a scored rule model."""
        return ScoredRuleModel(
            file=file_key,
            name=file_key,
            content=indexed_rule.content,
            tokens=indexed_rule.token_count,
            relevance_score=score,
            sections=indexed_rule.sections,
            source="local",
            priority=50,
            category=OptimizationRuleCategory.UNKNOWN,
        )

    def _get_local_rules_models(
        self, task_description: str, min_relevance_score: float
    ) -> list[ScoredRuleModel]:
        """Internal local rules helper returning typed models."""
        rules_index = self.indexer.get_index()
        if not rules_index:
            return []

        scored_rules: list[ScoredRuleModel] = []
        for file_key, rule_data in rules_index.items():
            try:
                indexed_rule = IndexedRuleModel.model_validate(rule_data)
                score = self.score_rule_relevance(
                    task_description, indexed_rule.content
                )
                if score < min_relevance_score:
                    continue
                scored_rules.append(
                    self._create_scored_rule(file_key, indexed_rule, score)
                )
            except Exception as e:
                logger.debug("_score_local_rules: skip rule: %s", e)
                continue

        scored_rules.sort(key=lambda r: r.relevance_score, reverse=True)
        return scored_rules

    # ---- delegation ---------------------------------------------------------

    async def stop_auto_reindex(self) -> None:
        """Stop automatic re-indexing task."""
        await self.indexer.stop_auto_reindex()

    def find_rule_files(self, rules_path: Path) -> list[Path]:
        """
        Find all rule files in the rules folder.

        Delegates to RulesIndexer.
        """
        return self.indexer.find_rule_files(rules_path)

    def parse_rule_sections(self, content: str) -> list[RuleSectionModel]:
        """
        Parse sections from rule content.

        Delegates to RulesIndexer.
        """
        return self.indexer.parse_rule_sections(content)

    def get_status(self) -> RulesManagerStatusModel:
        """
        Get status information about rules manager.

        Returns:
            RulesManagerStatusModel with manager status
        """
        indexer_status = self.indexer.get_status()
        return RulesManagerStatusModel(
            enabled=self.rules_folder is not None,
            rules_folder=self.rules_folder,
            indexed_files=indexer_status.indexed_files,
            last_indexed=indexer_status.last_indexed,
            auto_reindex_enabled=indexer_status.auto_reindex_enabled,
            reindex_interval_minutes=indexer_status.reindex_interval_minutes,
            total_tokens=indexer_status.total_tokens,
        )
