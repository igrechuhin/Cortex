"""
Approval Manager - Phase 5.3

Manage user approvals and preferences for refactoring suggestions.
"""

import json
from dataclasses import asdict, dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import cast

from cortex.core.async_file_utils import open_async_text_file


def _to_dict(obj: object) -> dict[str, object]:
    """Convert dataclass to dictionary with proper typing."""
    # Runtime check to ensure it's a dataclass
    if not hasattr(obj, "__dataclass_fields__"):
        raise TypeError(f"Object {type(obj).__name__} is not a dataclass")
    # Type checker cannot verify dataclass at static analysis time
    # but we've verified it at runtime above
    result = asdict(obj)  # type: ignore[arg-type]
    return cast(dict[str, object], result)


class ApprovalStatus(Enum):
    """Status of an approval."""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"
    APPLIED = "applied"


@dataclass
class Approval:
    """Approval record for a refactoring suggestion."""

    approval_id: str
    suggestion_id: str
    suggestion_type: str
    status: str
    created_at: str
    approved_at: str | None = None
    applied_at: str | None = None
    user_comment: str | None = None
    auto_apply: bool = False
    execution_id: str | None = None

    def to_dict(self) -> dict[str, object]:  # type: ignore[misc]
        """Convert to dictionary."""
        return _to_dict(self)


@dataclass
class ApprovalPreference:
    """User preference for auto-approvals."""

    pattern_type: str  # "consolidation", "split", "reorganization", etc.
    conditions: dict[str, object]  # type: ignore[misc]
    auto_approve: bool
    created_at: str

    def to_dict(self) -> dict[str, object]:  # type: ignore[misc]
        """Convert to dictionary."""
        return _to_dict(self)


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
        config: dict[str, object] | None = None,  # type: ignore[misc]
    ) -> None:
        self.memory_bank_dir: Path = Path(memory_bank_dir)
        self.config: dict[str, object] = config or {}  # type: ignore[misc]

        # Approval data file
        self.approval_file: Path = self.memory_bank_dir.parent / "approvals.json"

        # In-memory storage
        self.approvals: dict[str, Approval] = {}
        self.preferences: list[ApprovalPreference] = []

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
                data: dict[str, object] = cast(dict[str, object], json.load(f))

            self._load_approvals_from_data(data)
            self._load_preferences_from_data(data)

        except Exception as e:
            from cortex.core.logging_config import logger

            logger.warning(f"Approval file corrupted, starting fresh: {e}")

    def _load_approvals_from_data(self, data: dict[str, object]) -> None:
        """Load approvals from data dictionary.

        Args:
            data: Data dictionary from JSON file
        """
        approvals_dict: dict[str, object] = cast(
            dict[str, object], data.get("approvals", {})
        )
        for approval_id, approval_data in approvals_dict.items():
            approval_data_dict: dict[str, object] = cast(
                dict[str, object], approval_data
            )
            self.approvals[str(approval_id)] = self._create_approval_from_dict(
                approval_data_dict
            )

    def _create_approval_from_dict(self, approval_data: dict[str, object]) -> Approval:
        """Create Approval object from dictionary.

        Args:
            approval_data: Approval data dictionary

        Returns:
            Approval object
        """
        return Approval(
            approval_id=cast(str, approval_data.get("approval_id", "")),
            suggestion_id=cast(str, approval_data.get("suggestion_id", "")),
            suggestion_type=cast(str, approval_data.get("suggestion_type", "")),
            status=cast(str, approval_data.get("status", "pending")),
            created_at=cast(str, approval_data.get("created_at", "")),
            approved_at=cast(str | None, approval_data.get("approved_at")),
            applied_at=cast(str | None, approval_data.get("applied_at")),
            user_comment=cast(str | None, approval_data.get("user_comment")),
            auto_apply=cast(bool, approval_data.get("auto_apply", False)),
            execution_id=cast(str | None, approval_data.get("execution_id")),
        )

    def _load_preferences_from_data(self, data: dict[str, object]) -> None:
        """Load preferences from data dictionary.

        Args:
            data: Data dictionary from JSON file
        """
        preferences_list_raw: object = data.get("preferences", [])
        if not isinstance(preferences_list_raw, list):
            return

        for item_raw in cast(list[object], preferences_list_raw):
            if isinstance(item_raw, dict):
                item: dict[str, object] = cast(dict[str, object], item_raw)
                preference = self._create_preference_from_dict(item)
                if preference:
                    self.preferences.append(preference)

    def _create_preference_from_dict(
        self, pref_data: dict[str, object]
    ) -> ApprovalPreference | None:
        """Create ApprovalPreference object from dictionary.

        Args:
            pref_data: Preference data dictionary

        Returns:
            ApprovalPreference object or None if invalid
        """
        pattern_type = str(pref_data.get("pattern_type", ""))
        conditions_raw: object = pref_data.get("conditions", {})
        if not isinstance(conditions_raw, dict):
            return None

        conditions: dict[str, object] = cast(dict[str, object], conditions_raw)
        auto_approve = bool(pref_data.get("auto_approve", False))
        created_at = str(pref_data.get("created_at", ""))

        return ApprovalPreference(
            pattern_type=pattern_type,
            conditions=conditions,
            auto_approve=auto_approve,
            created_at=created_at,
        )

    async def _save_approvals(self) -> None:
        """Save approvals and preferences to disk."""
        try:
            approvals_dict: dict[str, dict[str, object]] = {}  # type: ignore[misc]
            for approval_id, approval in self.approvals.items():
                approvals_dict[approval_id] = approval.to_dict()

            preferences_list: list[dict[str, object]] = [  # type: ignore[misc]
                pref.to_dict() for pref in self.preferences
            ]

            data: dict[str, object] = {  # type: ignore[misc]
                "last_updated": datetime.now().isoformat(),
                "approvals": approvals_dict,
                "preferences": preferences_list,
            }

            async with open_async_text_file(self.approval_file, "w", "utf-8") as f:
                _ = await f.write(json.dumps(data, indent=2))

        except Exception as exc:
            raise Exception(f"Failed to save approvals: {exc}") from exc

    async def request_approval(
        self,
        suggestion_id: str,
        suggestion_type: str,
        auto_apply: bool = False,
    ) -> dict[str, object]:  # type: ignore[misc]
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
            ApprovalStatus.APPROVED.value
            if auto_approve
            else ApprovalStatus.PENDING.value
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
        status: str,
        auto_apply: bool,
        auto_approve: bool,
    ) -> Approval:
        """Create approval object."""
        return Approval(
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
        status: str,
        auto_approve: bool,
        auto_apply: bool,
    ) -> dict[str, object]:
        """Build approval response dictionary."""
        return {
            "approval_id": approval_id,
            "status": status,
            "auto_approved": auto_approve,
            "auto_apply": auto_apply,
            "message": (
                "Auto-approved based on preferences"
                if auto_approve
                else "Awaiting user approval"
            ),
        }

    async def approve_suggestion(
        self,
        suggestion_id: str,
        user_comment: str | None = None,
        auto_apply: bool = False,
    ) -> dict[str, object]:  # type: ignore[misc]
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
    ) -> tuple[Approval | None, str | None]:
        """Find pending approval for suggestion."""
        for aid, apr in self.approvals.items():
            if (
                apr.suggestion_id == suggestion_id
                and apr.status == ApprovalStatus.PENDING.value
            ):
                return apr, aid
        return None, None

    async def _create_missing_approval(
        self, suggestion_id: str, auto_apply: bool
    ) -> tuple[Approval, str]:
        """Create approval if not found."""
        result: dict[str, object] = await self.request_approval(
            suggestion_id, "unknown", auto_apply
        )  # type: ignore[misc]
        approval_id = cast(str, result["approval_id"])
        return self.approvals[approval_id], approval_id

    def _update_approval_status(
        self, approval: Approval, user_comment: str | None, auto_apply: bool
    ) -> None:
        """Update approval status."""
        approval.status = ApprovalStatus.APPROVED.value
        approval.approved_at = datetime.now().isoformat()
        approval.user_comment = user_comment
        approval.auto_apply = auto_apply

    def _build_approval_success_response(
        self, approval_id: str, suggestion_id: str, auto_apply: bool
    ) -> dict[str, object]:
        """Build approval success response."""
        return {
            "approval_id": approval_id,
            "status": "approved",
            "suggestion_id": suggestion_id,
            "auto_apply": auto_apply,
            "message": "Suggestion approved",
        }

    async def reject_suggestion(
        self,
        suggestion_id: str,
        user_comment: str | None = None,
    ) -> dict[str, object]:  # type: ignore[misc]
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
            return {
                "status": "error",
                "message": f"No approval found for suggestion {suggestion_id}",
            }

        # Update approval
        approval.status = ApprovalStatus.REJECTED.value
        approval.user_comment = user_comment

        await self._save_approvals()

        return {
            "approval_id": approval_id,
            "status": "rejected",
            "suggestion_id": suggestion_id,
            "message": "Suggestion rejected",
        }

    async def mark_as_applied(
        self,
        approval_id: str,
        execution_id: str,
    ) -> dict[str, object]:  # type: ignore[misc]
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
            return {
                "status": "error",
                "message": f"Approval {approval_id} not found",
            }

        approval.status = ApprovalStatus.APPLIED.value
        approval.applied_at = datetime.now().isoformat()
        approval.execution_id = execution_id

        await self._save_approvals()

        return {
            "approval_id": approval_id,
            "status": "applied",
            "execution_id": execution_id,
            "message": "Approval marked as applied",
        }

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
        conditions: dict[str, object] | None = None,  # type: ignore[misc]
    ) -> dict[str, object]:  # type: ignore[misc]
        """
        Add an auto-approval preference.

        Args:
            pattern_type: Type of refactoring (consolidation, split, etc.)
            auto_approve: Whether to auto-approve this type
            conditions: Optional conditions for auto-approval

        Returns:
            Created preference
        """
        preference = ApprovalPreference(
            pattern_type=pattern_type,
            conditions=conditions or {},
            auto_approve=auto_approve,
            created_at=datetime.now().isoformat(),
        )

        # Remove existing preference for this pattern type
        self.preferences = [
            p for p in self.preferences if p.pattern_type != pattern_type
        ]

        self.preferences.append(preference)
        await self._save_approvals()

        return {
            "status": "success",
            "pattern_type": pattern_type,
            "auto_approve": auto_approve,
            "message": f"Preference added for {pattern_type}",
        }

    async def remove_preference(
        self,
        pattern_type: str,
    ) -> dict[str, object]:  # type: ignore[misc]
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
            return {
                "status": "success",
                "pattern_type": pattern_type,
                "message": f"Preference removed for {pattern_type}",
            }
        else:
            return {
                "status": "not_found",
                "pattern_type": pattern_type,
                "message": f"No preference found for {pattern_type}",
            }

    async def get_preferences(self) -> dict[str, object]:  # type: ignore[misc]
        """
        Get all approval preferences.

        Returns:
            List of preferences
        """
        return {
            "preferences": [pref.to_dict() for pref in self.preferences],
            "count": len(self.preferences),
        }

    async def get_approval(self, approval_id: str) -> dict[str, object] | None:  # type: ignore[misc]
        """Get a specific approval by ID."""
        approval = self.approvals.get(approval_id)
        if approval:
            return approval.to_dict()
        return None

    async def get_approvals_for_suggestion(
        self, suggestion_id: str
    ) -> list[dict[str, object]]:  # type: ignore[misc]
        """Get all approvals for a specific suggestion."""
        approvals: list[dict[str, object]] = [  # type: ignore[misc]
            approval.to_dict()
            for approval in self.approvals.values()
            if approval.suggestion_id == suggestion_id
        ]
        return approvals

    async def get_pending_approvals(self) -> dict[str, object]:  # type: ignore[misc]
        """Get all pending approvals."""
        pending: list[dict[str, object]] = [  # type: ignore[misc]
            approval.to_dict()
            for approval in self.approvals.values()
            if approval.status == ApprovalStatus.PENDING.value
        ]

        return {
            "pending_approvals": pending,
            "count": len(pending),
        }

    async def get_approval_history(
        self,
        time_range_days: int = 90,
        status_filter: str | None = None,
    ) -> dict[str, object]:  # type: ignore[misc]
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

        filtered_approvals: list[dict[str, object]] = []  # type: ignore[misc]
        for approval in self.approvals.values():
            approval_date = datetime.fromisoformat(approval.created_at)
            if approval_date >= cutoff_date:
                if not status_filter or approval.status == status_filter:
                    filtered_approvals.append(approval.to_dict())

        # Calculate statistics
        total = len(filtered_approvals)
        approved = len([a for a in filtered_approvals if a.get("status") == "approved"])
        rejected = len([a for a in filtered_approvals if a.get("status") == "rejected"])
        pending = len([a for a in filtered_approvals if a.get("status") == "pending"])
        applied = len([a for a in filtered_approvals if a.get("status") == "applied"])

        def get_created_at(approval: dict[str, object]) -> str:  # type: ignore[misc]
            """Get created_at from approval dict."""
            return str(approval.get("created_at", ""))

        return {
            "time_range_days": time_range_days,
            "total_approvals": total,
            "approved": approved,
            "rejected": rejected,
            "pending": pending,
            "applied": applied,
            "approval_rate": approved / total if total > 0 else 0,
            "approvals": sorted(filtered_approvals, key=get_created_at, reverse=True),
        }

    async def cleanup_expired_approvals(
        self, expiry_days: int = 30
    ) -> dict[str, object]:  # type: ignore[misc]
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
            if approval.status == ApprovalStatus.PENDING.value:
                approval_date = datetime.fromisoformat(approval.created_at)
                if approval_date < cutoff_date:
                    approval.status = ApprovalStatus.EXPIRED.value
                    expired_count += 1

        if expired_count > 0:
            await self._save_approvals()

        return {
            "status": "success",
            "expired_count": expired_count,
            "expiry_days": expiry_days,
            "message": f"Expired {expired_count} old pending approvals",
        }
