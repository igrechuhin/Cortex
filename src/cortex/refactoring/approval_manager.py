"""
Approval Manager - Phase 5.3

Manage user approvals and preferences for refactoring suggestions.
"""

import json
from datetime import datetime
from pathlib import Path

from cortex.core.async_file_utils import open_async_text_file
from cortex.refactoring.models import (
    ApprovalConditions,
    ApprovalFileData,
    ApprovalHistoryResult,
    ApprovalManagerConfig,
    ApprovalModel,
    ApprovalPreferenceModel,
    ApprovalRequestResult,
    ApproveResult,
    CleanupExpiredApprovalsResult,
    MarkAppliedResult,
    PendingApprovalsResult,
    PreferenceResult,
    PreferencesListResult,
    RejectResult,
)
from cortex.refactoring.models import (
    ApprovalStatus as ApprovalStatusEnum,
)


class ApprovalManager:
    """
    Manage user approvals for refactoring suggestions.

    Features:
    - Track approval status for suggestions
    - Store user preferences for auto-approval
    - Maintain approval audit trail
    - Support approval workflows
    - Expire old approvals
    """

    def __init__(
        self,
        memory_bank_dir: Path,
        config: ApprovalManagerConfig | None = None,
    ) -> None:
        self.memory_bank_dir: Path = Path(memory_bank_dir)
        if config is None:
            self.config = ApprovalManagerConfig()
        else:
            self.config = config

        # Approval data file
        self.approval_file: Path = self.memory_bank_dir.parent / "approvals.json"

        # In-memory storage
        self.approvals: dict[str, ApprovalModel] = {}
        self.preferences: list[ApprovalPreferenceModel] = []

        # Load existing data
        self._load_approvals()

    def _load_approvals(self) -> None:
        """
        Load approvals and preferences from disk.

        Note:
            This method uses synchronous I/O during initialization for simplicity.
            For performance-critical paths, consider using async alternatives.
        """
        if not self.approval_file.exists():
            return

        try:
            with open(self.approval_file) as f:
                data = json.load(f)

            approval_file_data = ApprovalFileData.model_validate(data)
            self._load_approvals_from_data(approval_file_data)
            self._load_preferences_from_data(approval_file_data)

        except Exception as e:
            from cortex.core.logging_config import logger

            logger.warning(f"Approval file corrupted, starting fresh: {e}")

    def _load_approvals_from_data(self, data: ApprovalFileData) -> None:
        """Load approvals from ApprovalFileData.

        Args:
            data: ApprovalFileData model
        """
        for approval_id, approval_model in data.approvals.items():
            self.approvals[str(approval_id)] = approval_model

    def _load_preferences_from_data(self, data: ApprovalFileData) -> None:
        """Load preferences from ApprovalFileData.

        Args:
            data: ApprovalFileData model
        """
        self.preferences = list(data.preferences)

    async def _save_approvals(self) -> None:
        """Save approvals and preferences to disk."""
        try:
            approvals_dict: dict[str, ApprovalModel] = dict(self.approvals)
            preferences_list: list[ApprovalPreferenceModel] = list(self.preferences)

            data = ApprovalFileData(
                last_updated=datetime.now().isoformat(),
                approvals=approvals_dict,
                preferences=preferences_list,
            )

            async with open_async_text_file(self.approval_file, "w", "utf-8") as f:
                _ = await f.write(data.model_dump_json(indent=2))

        except Exception as exc:
            raise Exception(f"Failed to save approvals: {exc}") from exc

    async def request_approval(
        self,
        suggestion_id: str,
        suggestion_type: str,
        auto_apply: bool = False,
    ) -> ApprovalRequestResult:
        """
        Request approval for a refactoring suggestion.

        Args:
            suggestion_id: ID of the suggestion
            suggestion_type: Type of suggestion (consolidation, split, etc.)
            auto_apply: Whether to auto-apply after approval

        Returns:
            Approval record
        """
        approval_id = self._generate_approval_id(suggestion_id)
        auto_approve = self._check_auto_approval(suggestion_type)
        status = (
            ApprovalStatusEnum.APPROVED if auto_approve else ApprovalStatusEnum.PENDING
        )

        approval = self._create_approval(
            approval_id,
            suggestion_id,
            suggestion_type,
            status,
            auto_apply,
            auto_approve,
        )

        self.approvals[approval_id] = approval
        await self._save_approvals()

        return self._build_approval_response(
            approval_id, status, auto_approve, auto_apply
        )

    def _generate_approval_id(self, suggestion_id: str) -> str:
        """Generate unique approval ID with timestamp."""
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S%f")
        return f"apr-{suggestion_id}-{timestamp}"

    def _create_approval(
        self,
        approval_id: str,
        suggestion_id: str,
        suggestion_type: str,
        status: ApprovalStatusEnum,
        auto_apply: bool,
        auto_approve: bool,
    ) -> ApprovalModel:
        """Create approval model."""
        return ApprovalModel(
            approval_id=approval_id,
            suggestion_id=suggestion_id,
            suggestion_type=suggestion_type,
            status=status,
            created_at=datetime.now().isoformat(),
            approved_at=datetime.now().isoformat() if auto_approve else None,
            auto_apply=auto_apply,
        )

    def _build_approval_response(
        self,
        approval_id: str,
        status: ApprovalStatusEnum,
        auto_approve: bool,
        auto_apply: bool,
    ) -> ApprovalRequestResult:
        """Build approval response model."""
        return ApprovalRequestResult(
            approval_id=approval_id,
            status=status.value,
            auto_approved=auto_approve,
            auto_apply=auto_apply,
            message=(
                "Auto-approved based on preferences"
                if auto_approve
                else "Awaiting user approval"
            ),
        )

    async def approve_suggestion(
        self,
        suggestion_id: str,
        user_comment: str | None = None,
        auto_apply: bool = False,
    ) -> ApproveResult:
        """
        Approve a refactoring suggestion.

        Args:
            suggestion_id: ID of the suggestion to approve
            user_comment: Optional comment from user
            auto_apply: Whether to auto-apply after approval

        Returns:
            Updated approval record
        """
        approval, approval_id = self._find_pending_approval(suggestion_id)

        if not approval:
            approval, approval_id = await self._create_missing_approval(
                suggestion_id, auto_apply
            )

        self._update_approval_status(approval, user_comment, auto_apply)
        await self._save_approvals()

        if approval_id is None:
            raise ValueError("Approval ID is required but was None")

        return self._build_approval_success_response(
            approval_id, suggestion_id, auto_apply
        )

    def _find_pending_approval(
        self, suggestion_id: str
    ) -> tuple[ApprovalModel | None, str | None]:
        """Find pending approval for suggestion."""
        for aid, apr in self.approvals.items():
            if (
                apr.suggestion_id == suggestion_id
                and apr.status == ApprovalStatusEnum.PENDING
            ):
                return apr, aid
        return None, None

    async def _create_missing_approval(
        self, suggestion_id: str, auto_apply: bool
    ) -> tuple[ApprovalModel, str]:
        """Create approval if not found."""
        result = await self.request_approval(suggestion_id, "unknown", auto_apply)
        approval_id = result.approval_id
        return self.approvals[approval_id], approval_id

    def _update_approval_status(
        self, approval: ApprovalModel, user_comment: str | None, auto_apply: bool
    ) -> None:
        """Update approval status."""
        approval.status = ApprovalStatusEnum.APPROVED
        approval.approved_at = datetime.now().isoformat()
        approval.user_comment = user_comment
        approval.auto_apply = auto_apply

    def _build_approval_success_response(
        self, approval_id: str, suggestion_id: str, auto_apply: bool
    ) -> ApproveResult:
        """Build approval success response."""
        return ApproveResult(
            approval_id=approval_id,
            status="approved",
            suggestion_id=suggestion_id,
            auto_apply=auto_apply,
            message="Suggestion approved",
        )

    async def reject_suggestion(
        self,
        suggestion_id: str,
        user_comment: str | None = None,
    ) -> RejectResult:
        """
        Reject a refactoring suggestion.

        Args:
            suggestion_id: ID of the suggestion to reject
            user_comment: Optional comment explaining rejection

        Returns:
            Updated approval record
        """
        # Find approval for this suggestion
        approval = None
        approval_id = None

        for aid, apr in self.approvals.items():
            if apr.suggestion_id == suggestion_id:
                approval = apr
                approval_id = aid
                break

        if not approval:
            return RejectResult(
                status="error",
                suggestion_id=suggestion_id,
                message=f"No approval found for suggestion {suggestion_id}",
            )

        # Update approval
        approval.status = ApprovalStatusEnum.REJECTED
        approval.user_comment = user_comment

        await self._save_approvals()

        return RejectResult(
            status="rejected",
            approval_id=approval_id,
            suggestion_id=suggestion_id,
            message="Suggestion rejected",
        )

    async def mark_as_applied(
        self,
        approval_id: str,
        execution_id: str,
    ) -> MarkAppliedResult:
        """
        Mark an approval as applied.

        Args:
            approval_id: ID of the approval
            execution_id: ID of the execution

        Returns:
            Updated approval record
        """
        approval = self.approvals.get(approval_id)

        if not approval:
            return MarkAppliedResult(
                status="error",
                approval_id=approval_id,
                message=f"Approval {approval_id} not found",
            )

        approval.status = ApprovalStatusEnum.APPLIED
        approval.applied_at = datetime.now().isoformat()
        approval.execution_id = execution_id

        await self._save_approvals()

        return MarkAppliedResult(
            status="applied",
            approval_id=approval_id,
            execution_id=execution_id,
            message="Approval marked as applied",
        )

    def _check_auto_approval(self, suggestion_type: str) -> bool:
        """Check if a suggestion type should be auto-approved."""
        for preference in self.preferences:
            if preference.pattern_type == suggestion_type and preference.auto_approve:
                return True
        return False

    async def add_preference(
        self,
        pattern_type: str,
        auto_approve: bool,
        conditions: ApprovalConditions | None = None,
    ) -> PreferenceResult:
        """
        Add an auto-approval preference.

        Args:
            pattern_type: Type of refactoring (consolidation, split, etc.)
            auto_approve: Whether to auto-approve this type
            conditions: Optional conditions for auto-approval

        Returns:
            Created preference
        """
        if conditions is None:
            conditions = ApprovalConditions()

        preference = ApprovalPreferenceModel(
            pattern_type=pattern_type,
            conditions=conditions,
            auto_approve=auto_approve,
            created_at=datetime.now().isoformat(),
        )

        # Remove existing preference for this pattern type
        self.preferences = [
            p for p in self.preferences if p.pattern_type != pattern_type
        ]

        self.preferences.append(preference)
        await self._save_approvals()

        return PreferenceResult(
            status="success",
            pattern_type=pattern_type,
            auto_approve=auto_approve,
            message=f"Preference added for {pattern_type}",
        )

    async def remove_preference(
        self,
        pattern_type: str,
    ) -> PreferenceResult:
        """
        Remove an auto-approval preference.

        Args:
            pattern_type: Type of refactoring to remove preference for

        Returns:
            Removal status
        """
        original_count = len(self.preferences)
        self.preferences = [
            p for p in self.preferences if p.pattern_type != pattern_type
        ]

        removed = original_count - len(self.preferences)

        if removed > 0:
            await self._save_approvals()
            return PreferenceResult(
                status="success",
                pattern_type=pattern_type,
                message=f"Preference removed for {pattern_type}",
            )
        else:
            return PreferenceResult(
                status="not_found",
                pattern_type=pattern_type,
                message=f"No preference found for {pattern_type}",
            )

    async def get_preferences(self) -> PreferencesListResult:
        """
        Get all approval preferences.

        Returns:
            List of preferences
        """
        return PreferencesListResult(
            preferences=list(self.preferences),
            count=len(self.preferences),
        )

    async def get_approval(self, approval_id: str) -> ApprovalModel | None:
        """Get a specific approval by ID."""
        approval = self.approvals.get(approval_id)
        return approval

    async def get_approvals_for_suggestion(
        self, suggestion_id: str
    ) -> list[ApprovalModel]:
        """Get all approvals for a specific suggestion."""
        return [
            approval
            for approval in self.approvals.values()
            if approval.suggestion_id == suggestion_id
        ]

    async def get_pending_approvals(self) -> PendingApprovalsResult:
        """Get all pending approvals."""
        pending: list[ApprovalModel] = [
            approval
            for approval in self.approvals.values()
            if approval.status == ApprovalStatusEnum.PENDING
        ]

        return PendingApprovalsResult(
            pending_approvals=pending,
            count=len(pending),
        )

    async def get_approval_history(
        self,
        time_range_days: int = 90,
        status_filter: ApprovalStatusEnum | None = None,
    ) -> ApprovalHistoryResult:
        """
        Get approval history.

        Args:
            time_range_days: Number of days to include
            status_filter: Optional status filter

        Returns:
            Approval history with statistics
        """
        from datetime import timedelta

        cutoff_date = datetime.now() - timedelta(days=time_range_days)

        filtered_approvals: list[ApprovalModel] = []
        for approval in self.approvals.values():
            approval_date = datetime.fromisoformat(approval.created_at)
            if approval_date >= cutoff_date:
                if not status_filter or approval.status == status_filter:
                    filtered_approvals.append(approval)

        stats = self._calculate_approval_statistics(filtered_approvals)
        sorted_approvals = sorted(
            filtered_approvals, key=lambda a: a.created_at, reverse=True
        )
        return ApprovalHistoryResult(
            time_range_days=time_range_days,
            total_approvals=stats["total"],
            approved=stats["approved"],
            rejected=stats["rejected"],
            pending=stats["pending"],
            applied=stats["applied"],
            approval_rate=(
                stats["approved"] / stats["total"] if stats["total"] > 0 else 0.0
            ),
            approvals=sorted_approvals,
        )

    async def cleanup_expired_approvals(
        self, expiry_days: int = 30
    ) -> CleanupExpiredApprovalsResult:
        """
        Clean up old pending approvals.

        Args:
            expiry_days: Number of days after which to expire pending approvals

        Returns:
            Cleanup results
        """
        from datetime import timedelta

        cutoff_date = datetime.now() - timedelta(days=expiry_days)
        expired_count = 0

        for approval in self.approvals.values():
            if approval.status == ApprovalStatusEnum.PENDING:
                approval_date = datetime.fromisoformat(approval.created_at)
                if approval_date < cutoff_date:
                    approval.status = ApprovalStatusEnum.EXPIRED
                    expired_count += 1

        if expired_count > 0:
            await self._save_approvals()

        return CleanupExpiredApprovalsResult(
            status="success",
            expired_count=expired_count,
            expiry_days=expiry_days,
            message=f"Expired {expired_count} old pending approvals",
        )
