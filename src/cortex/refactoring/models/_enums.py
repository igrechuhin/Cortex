"""
Refactoring module enums.

Extracted from refactoring/models.py for Phase 9.1.2 file size compliance.
"""

from enum import Enum


class RefactoringType(str, Enum):
    """Types of refactoring suggestions."""

    CONSOLIDATION = "consolidation"
    SPLIT = "split"
    REORGANIZATION = "reorganization"
    TRANSCLUSION = "transclusion"
    RENAME = "rename"
    MERGE = "merge"


class RefactoringPriority(str, Enum):
    """Priority levels for refactoring suggestions."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    OPTIONAL = "optional"


class ApprovalStatus(str, Enum):
    """Status of an approval."""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"
    APPLIED = "applied"


class RefactoringStatus(str, Enum):
    """Status of a refactoring operation."""

    PENDING = "pending"
    VALIDATING = "validating"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


class RefactoringAction(str, Enum):
    """Action for apply_refactoring tool. Use instead of raw strings."""

    APPROVE = "approve"
    APPLY = "apply"
    ROLLBACK = "rollback"


class RefactoringSuggestionType(str, Enum):
    """Type for suggest_refactoring tool. Use instead of raw strings."""

    CONSOLIDATION = "consolidation"
    SPLITS = "splits"
    REORGANIZATION = "reorganization"


class FeedbackRecordStatus(str, Enum):
    """Status of a feedback record operation."""

    RECORDED = "recorded"
    ERROR = "error"


class RejectStatus(str, Enum):
    """Status of a reject operation."""

    REJECTED = "rejected"
    ERROR = "error"


class RollbackStatus(str, Enum):
    """Status of a rollback operation."""

    ROLLED_BACK = "rolled_back"
    ERROR = "error"
    NOT_FOUND = "not_found"


class RollbackHistoryStatus(str, Enum):
    """Status of a rollback history entry."""

    COMPLETED = "completed"
    FAILED = "failed"
    PARTIAL = "partial"


class MarkAppliedStatus(str, Enum):
    """Status of marking an approval as applied."""

    APPLIED = "applied"
    ERROR = "error"


class PreferenceStatus(str, Enum):
    """Status of a preference operation."""

    SUCCESS = "success"
    NOT_FOUND = "not_found"
    ERROR = "error"


class RollbackRefactoringStatus(str, Enum):
    """Status of a rollback refactoring result."""

    SUCCESS = "success"
    FAILED = "failed"


class ExecutionStatus(str, Enum):
    """Status of a refactoring execution."""

    SUCCESS = "success"
    FAILED = "failed"
    VALIDATION_FAILED = "validation_failed"


class LearningRate(str, Enum):
    """Learning rate setting."""

    AGGRESSIVE = "aggressive"
    MODERATE = "moderate"
    CONSERVATIVE = "conservative"
