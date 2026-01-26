"""
Pydantic models for rules module.

This module contains Pydantic models for rules operations,
including context detection, git operations, and synapse management.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

# ============================================================================
# Base Model
# ============================================================================


class RulesBaseModel(BaseModel):
    """Base model for rules types with strict validation."""

    model_config = ConfigDict(
        extra="forbid",
        validate_assignment=True,
        validate_default=True,
    )


# ============================================================================
# Git Command Models
# ============================================================================


class GitCommandResult(RulesBaseModel):
    """Result of a git command execution."""

    success: bool = Field(description="Whether command succeeded")
    stdout: str = Field(default="", description="Standard output")
    stderr: str = Field(default="", description="Standard error")
    returncode: int | None = Field(default=None, description="Process return code")
    error: str | None = Field(default=None, description="Error message if failed")


# ============================================================================
# Context Detection Models
# ============================================================================


class DetectedContext(RulesBaseModel):
    """Detected context for intelligent rule loading."""

    detected_languages: list[str] = Field(
        default_factory=list, description="Detected programming languages"
    )
    detected_frameworks: list[str] = Field(
        default_factory=list, description="Detected frameworks"
    )
    task_type: str | None = Field(default=None, description="Detected task type")
    categories_to_load: list[str] = Field(
        default_factory=list, description="Categories to load"
    )


# ============================================================================
# Synapse Repository Models
# ============================================================================


class SubmoduleInitResult(RulesBaseModel):
    """Result of submodule initialization."""

    model_config = ConfigDict(extra="allow", validate_assignment=True)

    status: Literal["success", "error"] = Field(description="Operation status")
    action: str | None = Field(
        default=None, description="Action performed (initialized, updated_existing)"
    )
    repo_url: str | None = Field(default=None, description="Repository URL")
    local_path: str | None = Field(default=None, description="Local path")
    submodule_added: bool | None = Field(
        default=None, description="Whether submodule was added"
    )
    initial_sync: bool | None = Field(
        default=None, description="Whether initial sync was performed"
    )
    categories_found: list[str] | None = Field(
        default=None, description="Categories found in manifest"
    )
    error: str | None = Field(default=None, description="Error message if failed")
    stdout: str | None = Field(default=None, description="Git stdout")
    stderr: str | None = Field(default=None, description="Git stderr")


class SyncChanges(RulesBaseModel):
    """Changes detected during sync."""

    added: list[str] = Field(default_factory=list, description="Added files")
    modified: list[str] = Field(default_factory=list, description="Modified files")
    deleted: list[str] = Field(default_factory=list, description="Deleted files")


class SyncResult(RulesBaseModel):
    """Result of repository sync operation."""

    status: Literal["success", "error"] = Field(description="Operation status")
    pulled: bool = Field(default=False, description="Whether pull was performed")
    pushed: bool = Field(default=False, description="Whether push was performed")
    changes: SyncChanges = Field(
        default_factory=SyncChanges, description="Changes detected"
    )
    error: str | None = Field(default=None, description="Error message if failed")


class UpdateResult(RulesBaseModel):
    """Result of update operation."""

    model_config = ConfigDict(extra="allow", validate_assignment=True)

    status: Literal["success", "error"] = Field(description="Operation status")
    file: str | None = Field(default=None, description="File updated")
    category: str | None = Field(default=None, description="Category of file")
    committed: bool = Field(default=False, description="Whether changes were committed")
    pushed: bool = Field(default=False, description="Whether changes were pushed")
    commit_hash: str | None = Field(
        default=None, description="Commit hash if committed"
    )
    message: str | None = Field(default=None, description="Commit message")
    type: str | None = Field(default=None, description="Type of update (rule/prompt)")
    error: str | None = Field(default=None, description="Error message if failed")


# ============================================================================
# Rules Loader Models
# ============================================================================


class RuleFileInfo(RulesBaseModel):
    """Information about a rule file."""

    file: str = Field(description="File path/name")
    content: str = Field(description="File content")
    tokens: int = Field(default=0, ge=0, description="Token count")
    category: str | None = Field(default=None, description="Rule category")
    source: Literal["local", "shared"] = Field(
        default="local", description="Rule source"
    )
    priority: int = Field(default=50, ge=0, description="Rule priority")
    relevance_score: float = Field(
        default=0.0, ge=0.0, le=1.0, description="Relevance score"
    )


class RuleMetadataEntry(RulesBaseModel):
    """Metadata entry for a rule in the manifest."""

    model_config = ConfigDict(extra="allow")  # Allow extra fields from manifest

    file: str = Field(description="Rule filename")
    priority: int = Field(default=50, ge=0, description="Rule priority")
    keywords: list[str] = Field(default_factory=list, description="Rule keywords")
    description: str = Field(default="", description="Rule description")


class CategoryInfo(RulesBaseModel):
    """Information about a rule category in the manifest."""

    model_config = ConfigDict(extra="allow")  # Allow extra fields from manifest

    rules: list[RuleMetadataEntry] = Field(
        default_factory=lambda: list[RuleMetadataEntry](),
        description="Rules in this category",
    )
    description: str = Field(default="", description="Category description")


class RulesManifestModel(RulesBaseModel):
    """Pydantic model for rules manifest structure."""

    model_config = ConfigDict(extra="allow")  # Allow extra fields from manifest

    version: str = Field(default="1.0", description="Manifest version")
    categories: dict[str, CategoryInfo] = Field(
        default_factory=dict, description="Categories and their rules"
    )
    metadata: dict[str, str] = Field(
        default_factory=dict, description="Additional metadata"
    )


class LoadedRule(RulesBaseModel):
    """A loaded rule with content and metadata."""

    category: str = Field(description="Rule category")
    file: str = Field(description="Rule filename")
    path: str = Field(description="Full path to rule file")
    content: str = Field(description="Rule content")
    priority: int = Field(default=50, ge=0, description="Rule priority")
    keywords: list[str] = Field(default_factory=list, description="Rule keywords")
    source: Literal["local", "shared"] = Field(
        default="shared", description="Rule source"
    )


# ============================================================================
# Prompts Loader Models
# ============================================================================


class PromptMetadataEntry(RulesBaseModel):
    """Metadata entry for a prompt in the manifest."""

    model_config = ConfigDict(extra="allow")  # Allow extra fields from manifest

    file: str = Field(description="Prompt filename")
    name: str = Field(default="", description="Prompt name")
    description: str = Field(default="", description="Prompt description")
    keywords: list[str] = Field(default_factory=list, description="Prompt keywords")


class PromptCategoryInfo(RulesBaseModel):
    """Information about a prompt category in the manifest."""

    model_config = ConfigDict(extra="allow")  # Allow extra fields from manifest

    prompts: list[PromptMetadataEntry] = Field(
        default_factory=lambda: list[PromptMetadataEntry](),
        description="Prompts in this category",
    )
    description: str = Field(default="", description="Category description")


class PromptsManifestModel(RulesBaseModel):
    """Pydantic model for prompts manifest structure."""

    model_config = ConfigDict(extra="allow")  # Allow extra fields from manifest

    version: str = Field(default="1.0", description="Manifest version")
    categories: dict[str, PromptCategoryInfo] = Field(
        default_factory=dict, description="Categories and their prompts"
    )


class LoadedPrompt(RulesBaseModel):
    """A loaded prompt with content and metadata."""

    file: str = Field(description="Prompt filename")
    name: str = Field(description="Prompt name")
    category: str = Field(description="Prompt category")
    description: str = Field(default="", description="Prompt description")
    keywords: list[str] = Field(default_factory=list, description="Keywords for search")
    content: str = Field(description="Prompt content")
    path: str = Field(description="Full path to prompt file")
    source: Literal["synapse"] = Field(default="synapse", description="Prompt source")


# ============================================================================
# Synapse Manager Models
# ============================================================================


class SynapseInitResult(RulesBaseModel):
    """Result of Synapse initialization."""

    status: Literal["success", "error", "already_initialized"] = Field(
        description="Operation status"
    )
    action: str | None = Field(default=None, description="Action performed")
    repo_url: str | None = Field(default=None, description="Repository URL")
    local_path: str | None = Field(default=None, description="Local path")
    submodule_added: bool = Field(
        default=False, description="Whether submodule was added"
    )
    manifest_loaded: bool = Field(
        default=False, description="Whether manifest was loaded"
    )
    error: str | None = Field(default=None, description="Error message if failed")


class SynapseSyncResult(RulesBaseModel):
    """Result of Synapse sync operation."""

    status: Literal["success", "error"] = Field(description="Operation status")
    pulled: bool = Field(default=False, description="Whether pull was performed")
    pushed: bool = Field(default=False, description="Whether push was performed")
    changes: SyncChanges = Field(
        default_factory=SyncChanges, description="Changes detected"
    )
    reindex_triggered: bool = Field(
        default=False, description="Whether reindex was triggered"
    )
    last_sync: str | None = Field(default=None, description="ISO timestamp of sync")
    error: str | None = Field(default=None, description="Error message if failed")


# ============================================================================
# Rule Creation Metadata Models
# ============================================================================


class RuleCreationMetadata(RulesBaseModel):
    """Metadata for creating a new rule.

    This model provides type-safe metadata for rule creation operations.
    """

    model_config = ConfigDict(extra="allow")  # Allow extra fields for flexibility

    priority: int = Field(default=50, ge=0, le=100, description="Rule priority (0-100)")
    keywords: list[str] = Field(
        default_factory=list, description="Rule keywords for search"
    )
    description: str = Field(default="", description="Rule description")
    author: str | None = Field(default=None, description="Author of the rule")
    version: str | None = Field(default=None, description="Rule version")
