"""
Rules management for custom project rules integration.

This module provides functionality to manage custom rules from a specified
folder (e.g., .cursorrules, .ai-rules) and make them available for
context optimization and relevance scoring. It delegates indexing operations
to RulesIndexer.
"""

from pathlib import Path
from typing import cast

from cortex.core.file_system import FileSystemManager
from cortex.core.metadata_index import MetadataIndex
from cortex.core.models import ModelDict
from cortex.core.token_counter import TokenCounter
from cortex.rules.synapse_manager import SynapseManager

from .models import (
    DetectedContextModel,
    IndexedRuleModel,
    RuleSectionModel,
    RulesManagerStatusModel,
    RulesResultModel,
    ScoredRuleModel,
)
from .rules_indexer import RulesIndexer


class RulesManager:
    """
    Manage custom rules from project folders.

    Enhanced to support both local rules and Synapse rules from git submodules.
    Delegates indexing operations to RulesIndexer.
    """

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
            rules_folder: Optional custom rules folder path (relative to project root)
            reindex_interval_minutes: How often to reindex rules (default: 30 min)
            synapse_manager: Optional Synapse manager for cross-project rules
        """
        self.project_root: Path = Path(project_root)
        self.file_system: FileSystemManager = file_system
        self.metadata_index: MetadataIndex = metadata_index
        self.token_counter: TokenCounter = token_counter
        self.rules_folder: str | None = rules_folder
        self.synapse_manager: SynapseManager | None = synapse_manager

        # Create indexer for rule file management
        self.indexer: RulesIndexer = RulesIndexer(
            project_root=project_root,
            token_counter=token_counter,
            reindex_interval_minutes=reindex_interval_minutes,
        )

    async def initialize(self) -> ModelDict:
        """
        Initialize rules manager and perform initial indexing.

        Returns:
            RulesIndexingResultModel with initialization status
        """
        if not self.rules_folder:
            message = "No rules folder configured"
            return {"status": "disabled", "message": message}

        rules_path = self.project_root / self.rules_folder
        if not rules_path.exists():
            message = f"Rules folder not found: {self.rules_folder}"
            return {"status": "not_found", "message": message}

        # Perform initial indexing
        result = await self.index_rules()

        # Start auto-reindexing
        await self.indexer.start_auto_reindex(self.rules_folder)

        return result

    async def index_rules(self, force: bool = False) -> ModelDict:
        """
        Index all rules files from the configured folder.

        Delegates to RulesIndexer.

        Args:
            force: Force reindexing even if recently indexed

        Returns:
            RulesIndexingResultModel with indexing results
        """
        if not self.rules_folder:
            error = "No rules folder configured"
            return {"status": "error", "error": error, "message": error}

        return await self.indexer.index_rules(self.rules_folder, force)

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

        Enhanced to support both local and shared rules with context detection.

        Args:
            task_description: Description of the task
            max_tokens: Maximum tokens to include
            min_relevance_score: Minimum relevance score to include
            project_files: Optional list of project files for context detection
            rule_priority: "local_overrides_shared" or "shared_overrides_local"
            context_aware: Enable intelligent context detection

        Returns:
            RulesResultModel with categorized rules and context information
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
        """Initialize result structure with default values.

        Returns:
            RulesResultModel with empty structure
        """
        return RulesResultModel(
            generic_rules=[],
            language_rules=[],
            local_rules=[],
            total_tokens=0,
            context=DetectedContextModel(),
            source="local_only",
        )

    async def _get_hybrid_rules(
        self,
        result: RulesResultModel,
        task_description: str,
        max_tokens: int,
        min_relevance_score: float,
        project_files: list[Path] | None,
        rule_priority: str,
    ) -> RulesResultModel:
        """Get rules using hybrid (shared + local) approach."""
        # Detect context
        context = await self._detect_and_load_context(
            result, task_description, project_files
        )

        # Load and merge rules
        selected_rules = await self._load_and_merge_rules(
            task_description, max_tokens, min_relevance_score, rule_priority, context
        )

        # Categorize rules
        self._categorize_rules(result, selected_rules, context)

        # Calculate total tokens
        result.total_tokens = self._calculate_total_tokens(selected_rules)

        return result

    async def _detect_and_load_context(
        self,
        result: RulesResultModel,
        task_description: str,
        project_files: list[Path] | None,
    ) -> DetectedContextModel:
        """Detect context and update result structure."""
        assert self.synapse_manager is not None  # Already checked in caller
        context_dict = await self.synapse_manager.detect_context(
            task_description, project_files
        )
        # Convert dict to model
        if isinstance(context_dict, dict):
            normalized: ModelDict = dict(context_dict)
            # Some legacy callers/tests use `frameworks` instead of
            # `detected_frameworks`.
            if "frameworks" in normalized and "detected_frameworks" not in normalized:
                normalized["detected_frameworks"] = normalized.get("frameworks", [])
            _ = normalized.pop("frameworks", None)
            context = DetectedContextModel.model_validate(normalized)
        else:
            context = DetectedContextModel.model_validate(
                cast(ModelDict, context_dict.model_dump(mode="json"))
            )
        result.context = context
        result.source = "hybrid"
        return context

    async def _load_and_merge_rules(
        self,
        task_description: str,
        max_tokens: int,
        min_relevance_score: float,
        rule_priority: str,
        context: DetectedContextModel,
    ) -> list[ScoredRuleModel]:
        """Load shared and local rules, merge them, and select within budget."""
        # Load shared rules
        shared_rules = await self._load_shared_rules(context)

        # Get local rules
        local_rules = await self._get_tagged_local_rules(
            task_description, min_relevance_score
        )

        # Merge rules
        assert self.synapse_manager is not None  # Already checked in caller
        shared_rules_dicts: list[ModelDict] = [
            cast(ModelDict, rule.model_dump(mode="json")) for rule in shared_rules
        ]
        local_rules_dicts: list[ModelDict] = [
            cast(ModelDict, rule.model_dump(mode="json")) for rule in local_rules
        ]
        merged_rule_dicts = await self.synapse_manager.merge_rules(
            shared_rules=shared_rules_dicts,
            local_rules=local_rules_dicts,
            priority=rule_priority,
        )
        merged_rules = [
            ScoredRuleModel.model_validate(rule) for rule in merged_rule_dicts
        ]

        # Select within token budget
        return await self._select_within_budget_models(
            merged_rules, task_description, max_tokens, min_relevance_score
        )

    async def _load_shared_rules(
        self, context: DetectedContextModel
    ) -> list[ScoredRuleModel]:
        """Load shared rules based on detected context."""
        assert self.synapse_manager is not None  # Already checked in caller
        categories = await self.synapse_manager.get_relevant_categories(
            cast(ModelDict, context.model_dump(mode="json"))
        )

        shared_rules: list[ScoredRuleModel] = []
        for category in categories:
            category_rules = await self.synapse_manager.load_category(category)
            # Convert LoadedRule models to ScoredRuleModel
            for loaded_rule in category_rules:
                try:
                    # Calculate tokens for the rule content
                    tokens = self.token_counter.count_tokens(loaded_rule.content)
                    shared_rules.append(
                        ScoredRuleModel(
                            file=loaded_rule.file,
                            name=loaded_rule.file,
                            content=loaded_rule.content,
                            tokens=tokens,
                            relevance_score=0.0,  # Will be calculated later
                            sections=[],
                            source="shared",
                            priority=loaded_rule.priority,
                            category=loaded_rule.category,
                        )
                    )
                except Exception:
                    # Skip invalid rules
                    continue

        return shared_rules

    async def _get_tagged_local_rules(
        self, task_description: str, min_relevance_score: float
    ) -> list[ScoredRuleModel]:
        """Get local rules and tag them with source."""
        local_rules = self._get_local_rules_models(
            task_description, min_relevance_score
        )

        # Tag rules with source - update models
        for rule in local_rules:
            rule.source = "local"

        return local_rules

    def _categorize_rules(
        self,
        result: RulesResultModel,
        selected_rules: list[ScoredRuleModel],
        context: DetectedContextModel,
    ) -> None:
        """Categorize selected rules into generic, language, and local categories."""
        generic_rules: list[ScoredRuleModel] = []
        language_rules: list[ScoredRuleModel] = []
        local_rules: list[ScoredRuleModel] = []

        for rule in selected_rules:
            if rule.category == "generic":
                generic_rules.append(rule)
                continue

            self._categorize_non_generic_rule(
                rule, context, language_rules, local_rules
            )

        result.generic_rules = generic_rules
        result.language_rules = language_rules
        result.local_rules = local_rules

    def _categorize_non_generic_rule(
        self,
        rule: ScoredRuleModel,
        context: DetectedContextModel,
        language_rules: list[ScoredRuleModel],
        local_rules: list[ScoredRuleModel],
    ) -> None:
        """Categorize a non-generic rule into language or local categories.

        Args:
            rule: Rule model to categorize
            context: Context model with detected languages
            language_rules: List to append language rules to
            local_rules: List to append local rules to
        """
        if rule.category in context.detected_languages:
            language_rules.append(rule)

        if rule.source == "local":
            local_rules.append(rule)

    def _calculate_total_tokens(self, rules: list[ScoredRuleModel]) -> int:
        """Calculate total tokens from rules."""
        return sum(rule.tokens for rule in rules)

    # _build_rules_result is no longer needed - result is already a RulesResultModel

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

        # Select within token budget
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
            category="",
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
            except Exception:
                continue

        scored_rules.sort(key=lambda r: r.relevance_score, reverse=True)
        return scored_rules

    async def select_within_budget(
        self,
        rules: list[ScoredRuleModel],
        task_description: str,
        max_tokens: int,
        min_relevance_score: float,
    ) -> list[ScoredRuleModel]:
        """
        Select rules within token budget with relevance scoring.

        Args:
            rules: List of rules to select from
            task_description: Task description for scoring
            max_tokens: Maximum token budget
            min_relevance_score: Minimum relevance score

        Returns:
            Selected rules within budget
        """
        return await self._select_within_budget_models(
            rules, task_description, max_tokens, min_relevance_score
        )

    async def _select_within_budget_models(
        self,
        rules: list[ScoredRuleModel],
        task_description: str,
        max_tokens: int,
        min_relevance_score: float,
    ) -> list[ScoredRuleModel]:
        """Select rules within budget returning typed models (internal)."""
        _score_rules_if_needed(self, rules, task_description)
        filtered_rules = _filter_rules_by_score(rules, min_relevance_score)
        filtered_rules.sort(
            key=lambda x: (x.priority, x.relevance_score),
            reverse=True,
        )
        return _select_rules_within_budget(self, filtered_rules, max_tokens)

    async def get_all_rules(self) -> dict[str, IndexedRuleModel]:
        """
        Get all indexed rules.

        Returns:
            Dictionary mapping file keys to indexed rule models
        """
        return self.indexer.get_index()

    def score_rule_relevance(self, task_description: str, rule_content: str) -> float:
        """
        Score rule relevance to task description.

        Args:
            task_description: Task description
            rule_content: Rule content

        Returns:
            Relevance score (0.0 - 1.0)
        """
        # Simple keyword-based scoring
        task_lower = task_description.lower()
        rule_lower = rule_content.lower()

        # Extract keywords from task
        task_words = set(task_lower.split())

        # Remove common stop words
        stop_words = {
            "the",
            "a",
            "an",
            "and",
            "or",
            "but",
            "in",
            "on",
            "at",
            "to",
            "for",
        }
        task_words = {w for w in task_words if len(w) > 2 and w not in stop_words}

        if not task_words:
            return 0.0

        # Count matches
        matches = sum(1 for word in task_words if word in rule_lower)

        # Calculate score
        score = matches / len(task_words)

        return min(score, 1.0)

    async def stop_auto_reindex(self):
        """Stop automatic re-indexing task."""
        await self.indexer.stop_auto_reindex()

    def find_rule_files(self, rules_path: Path) -> list[Path]:
        """
        Find all rule files in the rules folder.

        Delegates to RulesIndexer.

        Args:
            rules_path: Path to rules folder

        Returns:
            List of rule file paths
        """
        return self.indexer.find_rule_files(rules_path)

    def parse_rule_sections(self, content: str) -> list[RuleSectionModel]:
        """
        Parse sections from rule content.

        Delegates to RulesIndexer.

        Args:
            content: Rule file content

        Returns:
            List of RuleSectionModel with metadata
        """
        return self.indexer.parse_rule_sections(content)

    def get_status(self) -> RulesManagerStatusModel:
        """
        Get status information about rules manager.

        Returns:
            RulesManagerStatusModel with manager status
        """
        indexer_status = self.indexer.get_status()

        # Combine indexer status with manager-specific fields
        return RulesManagerStatusModel(
            enabled=self.rules_folder is not None,
            rules_folder=self.rules_folder,
            indexed_files=indexer_status.indexed_files,
            last_indexed=indexer_status.last_indexed,
            auto_reindex_enabled=indexer_status.auto_reindex_enabled,
            reindex_interval_minutes=indexer_status.reindex_interval_minutes,
            total_tokens=indexer_status.total_tokens,
        )


def _score_rules_if_needed(
    manager: RulesManager, rules: list[ScoredRuleModel], task_description: str
) -> None:
    """Score rules if they don't have a score yet."""
    for rule in rules:
        if rule.relevance_score == 0.0:
            rule.relevance_score = manager.score_rule_relevance(
                task_description, rule.content
            )


def _filter_rules_by_score(
    rules: list[ScoredRuleModel], min_relevance_score: float
) -> list[ScoredRuleModel]:
    """Filter rules by minimum relevance score."""
    return [r for r in rules if r.relevance_score >= min_relevance_score]


def _select_rules_within_budget(
    manager: RulesManager,
    filtered_rules: list[ScoredRuleModel],
    max_tokens: int,
) -> list[ScoredRuleModel]:
    """Select rules within token budget."""
    selected_rules: list[ScoredRuleModel] = []
    total_tokens = 0

    for rule in filtered_rules:
        rule_tokens = rule.tokens

        if rule_tokens == 0:
            rule_tokens = manager.token_counter.count_tokens(rule.content)
            rule.tokens = rule_tokens

        if total_tokens + rule_tokens <= max_tokens:
            selected_rules.append(rule)
            total_tokens += rule_tokens
        else:
            break

    return selected_rules
