#!/usr/bin/env python3
"""Refactoring execution protocols for MCP Memory Bank.

This module defines Protocol classes (PEP 544) for refactoring execution,
approval management, rollback operations, and learning from feedback.
"""

from typing import Protocol

from cortex.refactoring.models import (
    ApprovalRequestDetails,
    ApprovalRequestResult,
    ApprovalStatusResult,
    ApproveResult,
    ConfidenceAdjustmentResult,
    FeedbackData,
    FeedbackRecordResult,
    LearningInsights,
    RollbackHistoryEntry,
    RollbackRefactoringResult,
)


class ApprovalManagerProtocol(Protocol):
    """Protocol for refactoring approval operations using structural
    subtyping (PEP 544).

    This protocol defines the interface for managing approval workflows for
    refactoring operations. Approval management ensures safe execution with
    user oversight. A class implementing these methods automatically satisfies
    this protocol.

    Used by:
        - ApprovalManager: Manages approval requests and status tracking
        - RefactoringExecutor: For checking approval before execution
        - MCP Tools: For approve_refactoring operations
        - Client Applications: For approval workflow UI

    Example implementation:
        ```python
        class SimpleApprovalManager:
            def __init__(self):
                self.approvals = {}

            async def request_approval(
                self, refactoring_id: str, details: ApprovalRequestDetails
            ) -> ApprovalRequestResult:
                self.approvals[refactoring_id] = {
                    "status": "pending",
                    "details": details,
                    "requested_at": datetime.utcnow().isoformat(),
                }
                return ApprovalRequestResult(
                    approval_id=refactoring_id,
                    status="pending",
                    message="Approval requested",
                )

            async def get_approval_status(
                self, refactoring_id: str
            ) -> ApprovalStatusResult:
                if refactoring_id not in self.approvals:
                    return ApprovalStatusResult(
                        approval_id=refactoring_id,
                        status="not_found",
                        suggestion_id="",
                        suggestion_type="",
                        created_at="",
                    )
                approval = self.approvals[refactoring_id]
                return ApprovalStatusResult(
                    approval_id=refactoring_id,
                    status=approval["status"],
                    suggestion_id=refactoring_id,
                    suggestion_type="",
                    created_at=approval.get("requested_at", ""),
                )

            async def approve(self, refactoring_id: str) -> ApproveResult:
                if refactoring_id not in self.approvals:
                    return ApproveResult(
                        approval_id=refactoring_id,
                        status="error",
                        suggestion_id=refactoring_id,
                        message="Refactoring not found",
                    )

                self.approvals[refactoring_id]["status"] = "approved"
                self.approvals[refactoring_id]["approved_at"] = (
                    datetime.utcnow().isoformat()
                )

                return ApproveResult(
                    approval_id=refactoring_id,
                    status="approved",
                    suggestion_id=refactoring_id,
                    message="Refactoring approved",
                )

        # SimpleApprovalManager automatically satisfies ApprovalManagerProtocol
        ```

    Note:
        - Tracks approval status per refactoring
        - Timestamps for audit trail
        - Prevents execution without approval
    """

    async def request_approval(
        self, refactoring_id: str, details: ApprovalRequestDetails
    ) -> ApprovalRequestResult:
        """Request approval for refactoring.

        Args:
            refactoring_id: Unique refactoring identifier
            details: Refactoring details

        Returns:
            Approval request result model
        """
        ...

    async def get_approval_status(self, refactoring_id: str) -> ApprovalStatusResult:
        """Get approval status for refactoring.

        Args:
            refactoring_id: Unique refactoring identifier

        Returns:
            Approval status result model
        """
        ...

    async def approve(self, refactoring_id: str) -> ApproveResult:
        """Approve refactoring execution.

        Args:
            refactoring_id: Unique refactoring identifier

        Returns:
            Approval result model
        """
        ...


class RollbackManagerProtocol(Protocol):
    """Protocol for rollback operations using structural subtyping (PEP 544).

    This protocol defines the interface for rolling back refactoring operations
    and tracking rollback history. Rollback capability provides safety and
    confidence when executing refactorings. A class implementing these methods
    automatically satisfies this protocol.

    Used by:
        - RollbackManager: Manages rollback operations with history tracking
        - RefactoringExecutor: For providing rollback capability
        - MCP Tools: For rollback_refactoring operations
        - Client Applications: For undo functionality

    Example implementation:
        ```python
        class SimpleRollbackManager:
            def __init__(self, version_manager: VersionManagerProtocol):
                self.version_manager = version_manager
                self.rollback_history = []

            async def rollback_refactoring(
                self, execution_id: str
            ) -> RollbackRefactoringResult:
                # Find and restore snapshots
                snapshot_ids = self._get_snapshots_for_execution(execution_id)
                rolled_back = []
                for snapshot_id in snapshot_ids:
                    result = await self.version_manager.rollback_to_version(snapshot_id)
                    rolled_back.append(result.file_name)

                # Record in history
                self.rollback_history.append({
                    "execution_id": execution_id,
                    "files": rolled_back,
                    "timestamp": datetime.utcnow().isoformat(),
                })

                return RollbackRefactoringResult(
                    status="rolled_back",
                    execution_id=execution_id,
                    files_restored=len(rolled_back),
                    files_list=rolled_back,
                    timestamp=datetime.utcnow().isoformat(),
                )

            async def get_rollback_history(self) -> list[RollbackHistoryEntry]:
                return [
                    RollbackHistoryEntry(
                        rollback_id=f"rb-{i}",
                        execution_id=entry["execution_id"],
                        files=entry["files"],
                        timestamp=entry["timestamp"],
                        status="completed",
                    )
                    for i, entry in enumerate(
                        sorted(
                            self.rollback_history,
                            key=lambda x: x["timestamp"],
                            reverse=True,
                        )
                    )
                ]

        # SimpleRollbackManager automatically satisfies RollbackManagerProtocol
        ```

    Note:
        - Restores all files modified by refactoring
        - Maintains rollback history for audit
        - Enables safe experimentation
    """

    async def rollback_refactoring(
        self, execution_id: str
    ) -> RollbackRefactoringResult:
        """Rollback a refactoring operation.

        Args:
            execution_id: Execution identifier to rollback

        Returns:
            Rollback result model
        """
        ...

    async def get_rollback_history(self) -> list[RollbackHistoryEntry]:
        """Get history of rollback operations.

        Returns:
            List of rollback history entry models
        """
        ...


class LearningEngineProtocol(Protocol):
    """Protocol for learning and adaptation operations using structural
    subtyping (PEP 544).

    This protocol defines the interface for learning from user feedback on
    refactoring suggestions and adapting suggestion confidence scores. Learning
    enables continuous improvement of refactoring recommendations. A class
    implementing these methods automatically satisfies this protocol.

    Used by:
        - LearningEngine: Tracks feedback and adjusts confidence scores
        - RefactoringEngine: For confidence-based suggestion ranking
        - MCP Tools: For submit_feedback and get_learning_stats operations
        - Client Applications: For feedback collection

    Example implementation:
        ```python
        class SimpleLearningEngine:
            def __init__(self):
                self.feedback_history = []
                self.pattern_confidence = {}

            async def record_feedback(
                self,
                suggestion_id: str,
                accepted: bool,
                reason: str | None = None,
                additional_data: FeedbackData | None = None,
            ) -> FeedbackRecordResult:
                feedback = {
                    "suggestion_id": suggestion_id,
                    "accepted": accepted,
                    "reason": reason,
                    "timestamp": datetime.utcnow().isoformat(),
                }
                self.feedback_history.append(feedback)

                # Auto-adjust confidence
                pattern = self._extract_pattern(suggestion_id)
                adjustment = 0.1 if accepted else -0.1
                await self.adjust_suggestion_confidence(
                    pattern["type"], pattern["pattern"], adjustment
                )

                return FeedbackRecordResult(
                    status="recorded",
                    feedback_id=f"fb-{suggestion_id}",
                )

            async def adjust_suggestion_confidence(
                self,
                suggestion_type: str,
                pattern: str,
                adjustment: float,
            ) -> ConfidenceAdjustmentResult:
                key = f"{suggestion_type}:{pattern}"
                current = self.pattern_confidence.get(key, 0.5)
                new_confidence = max(0.0, min(1.0, current + adjustment))
                self.pattern_confidence[key] = new_confidence
                return ConfidenceAdjustmentResult(
                    original_confidence=current,
                    adjusted_confidence=new_confidence,
                    reason=f"Adjusted by {adjustment}",
                )

            async def get_learning_insights(self) -> LearningInsights:
                total = len(self.feedback_history)
                accepted = sum(1 for f in self.feedback_history if f["accepted"])
                return LearningInsights(
                    total_feedback=total,
                    approval_rate=accepted / total if total > 0 else 0.0,
                )

        # SimpleLearningEngine automatically satisfies LearningEngineProtocol
        ```

    Note:
        - Tracks user feedback for continuous improvement
        - Adjusts confidence scores based on acceptance rates
        - Provides learning insights and statistics
    """

    async def record_feedback(
        self,
        suggestion_id: str,
        accepted: bool,
        reason: str | None = None,
        additional_data: FeedbackData | None = None,
    ) -> FeedbackRecordResult:
        """Record user feedback on a suggestion.

        Args:
            suggestion_id: Suggestion identifier
            accepted: Whether suggestion was accepted
            reason: Optional reason for decision
            additional_data: Optional additional feedback data

        Returns:
            Feedback record result model
        """
        ...

    async def adjust_suggestion_confidence(
        self,
        suggestion_type: str,
        pattern: str,
        adjustment: float,
    ) -> ConfidenceAdjustmentResult:
        """Adjust confidence for a suggestion pattern.

        Args:
            suggestion_type: Type of suggestion
            pattern: Pattern identifier
            adjustment: Confidence adjustment value

        Returns:
            Confidence adjustment result model
        """
        ...

    async def get_learning_insights(self) -> LearningInsights:
        """Get learning insights and statistics.

        Returns:
            Learning insights model
        """
        ...


__all__ = [
    "ApprovalManagerProtocol",
    "RollbackManagerProtocol",
    "LearningEngineProtocol",
]
