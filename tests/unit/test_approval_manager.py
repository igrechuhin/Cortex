"""Unit tests for ApprovalManager - Phase 5.3"""

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import cast

import pytest

from cortex.refactoring.approval_manager import (
    Approval,
    ApprovalManager,
    ApprovalPreference,
    ApprovalStatus,
)


class TestApprovalStatus:
    """Test ApprovalStatus enum."""

    def test_status_values(self):
        """Test approval status enum values."""
        # Assert
        assert ApprovalStatus.PENDING.value == "pending"
        assert ApprovalStatus.APPROVED.value == "approved"
        assert ApprovalStatus.REJECTED.value == "rejected"
        assert ApprovalStatus.EXPIRED.value == "expired"
        assert ApprovalStatus.APPLIED.value == "applied"


class TestApprovalDataclass:
    """Test Approval dataclass."""

    def test_approval_to_dict(self):
        """Test converting approval to dictionary."""
        # Arrange
        approval = Approval(
            approval_id="apr-1",
            suggestion_id="sug-1",
            suggestion_type="consolidation",
            status="approved",
            created_at="2025-01-01T12:00:00",
        )

        # Act
        result = approval.to_dict()

        # Assert
        assert result["approval_id"] == "apr-1"
        assert result["suggestion_id"] == "sug-1"
        assert result["status"] == "approved"


class TestApprovalPreferenceDataclass:
    """Test ApprovalPreference dataclass."""

    def test_preference_to_dict(self):
        """Test converting preference to dictionary."""
        # Arrange
        preference = ApprovalPreference(
            pattern_type="consolidation",
            conditions={"min_confidence": 0.8},
            auto_approve=True,
            created_at="2025-01-01T12:00:00",
        )

        # Act
        result = preference.to_dict()

        # Assert
        assert result["pattern_type"] == "consolidation"
        assert result["auto_approve"] is True


class TestApprovalManagerInitialization:
    """Test ApprovalManager initialization."""

    @pytest.mark.asyncio
    async def test_initialization_creates_empty_state(self, memory_bank_dir: Path):
        """Test manager initialization with no existing data."""
        # Arrange & Act
        manager = ApprovalManager(memory_bank_dir=memory_bank_dir)

        # Assert
        assert manager.memory_bank_dir == Path(memory_bank_dir)
        assert len(manager.approvals) == 0
        assert len(manager.preferences) == 0

    @pytest.mark.asyncio
    async def test_initialization_loads_existing_data(self, memory_bank_dir: Path):
        """Test manager loads existing approval data."""
        # Arrange
        approval_file = memory_bank_dir.parent / "approvals.json"
        approval_data: dict[str, object] = {
            "approvals": {
                "apr-1": {
                    "approval_id": "apr-1",
                    "suggestion_id": "sug-1",
                    "suggestion_type": "consolidation",
                    "status": "approved",
                    "created_at": "2025-01-01T12:00:00",
                }
            },
            "preferences": [
                {
                    "pattern_type": "split",
                    "conditions": {},
                    "auto_approve": True,
                    "created_at": "2025-01-01T12:00:00",
                }
            ],
        }
        # Create parent directory
        approval_file.parent.mkdir(parents=True, exist_ok=True)
        _ = approval_file.write_text(json.dumps(approval_data))

        # Act
        manager = ApprovalManager(memory_bank_dir=memory_bank_dir)

        # Assert
        assert len(manager.approvals) == 1
        assert "apr-1" in manager.approvals
        assert len(manager.preferences) == 1


class TestRequestApproval:
    """Test requesting approval for suggestions."""

    @pytest.mark.asyncio
    async def test_request_approval_creates_pending_approval(
        self, memory_bank_dir: Path
    ):
        """Test requesting approval creates pending approval."""
        # Arrange
        manager = ApprovalManager(memory_bank_dir=memory_bank_dir)

        # Act
        result = await manager.request_approval(
            suggestion_id="sug-1",
            suggestion_type="consolidation",
            auto_apply=False,
        )

        # Assert
        assert result["status"] == "pending"
        assert result["auto_approved"] is False
        assert "approval_id" in result

    @pytest.mark.asyncio
    async def test_request_approval_with_auto_approve_preference(
        self, memory_bank_dir: Path
    ):
        """Test request approval auto-approves when preference set."""
        # Arrange
        manager = ApprovalManager(memory_bank_dir=memory_bank_dir)

        # Add auto-approve preference
        _ = await manager.add_preference(
            pattern_type="consolidation", auto_approve=True
        )

        # Act
        result = await manager.request_approval(
            suggestion_id="sug-1",
            suggestion_type="consolidation",
            auto_apply=False,
        )

        # Assert
        assert result["status"] == "approved"
        assert result["auto_approved"] is True

    @pytest.mark.asyncio
    async def test_request_approval_saves_to_disk(self, memory_bank_dir: Path):
        """Test request approval persists to disk."""
        # Arrange
        # Ensure .cortex directory exists
        (memory_bank_dir.parent / ".cortex").mkdir(parents=True, exist_ok=True)
        manager = ApprovalManager(memory_bank_dir=memory_bank_dir)

        # Act
        _ = await manager.request_approval(
            suggestion_id="sug-1",
            suggestion_type="split",
            auto_apply=True,
        )

        # Assert
        approval_file = memory_bank_dir.parent / "approvals.json"
        assert approval_file.exists()
        data = json.loads(approval_file.read_text())
        assert len(data["approvals"]) == 1


class TestApproveSuggestion:
    """Test approving suggestions."""

    @pytest.mark.asyncio
    async def test_approve_pending_suggestion(self, memory_bank_dir: Path):
        """Test approving a pending suggestion."""
        # Arrange
        manager = ApprovalManager(memory_bank_dir=memory_bank_dir)
        _ = await manager.request_approval(
            suggestion_id="sug-1", suggestion_type="consolidation"
        )

        # Act
        result = await manager.approve_suggestion(
            suggestion_id="sug-1",
            user_comment="Looks good",
            auto_apply=True,
        )

        # Assert
        assert result["status"] == "approved"
        assert result["auto_apply"] is True

    @pytest.mark.asyncio
    async def test_approve_nonexistent_suggestion_creates_approval(
        self, memory_bank_dir: Path
    ):
        """Test approving nonexistent suggestion creates new approval."""
        # Arrange
        manager = ApprovalManager(memory_bank_dir=memory_bank_dir)

        # Act
        result = await manager.approve_suggestion(
            suggestion_id="sug-1", user_comment="Approved"
        )

        # Assert
        assert result["status"] == "approved"
        assert len(manager.approvals) == 1

    @pytest.mark.asyncio
    async def test_approve_updates_approval_timestamp(self, memory_bank_dir: Path):
        """Test approval updates approved_at timestamp."""
        # Arrange
        manager = ApprovalManager(memory_bank_dir=memory_bank_dir)
        _ = await manager.request_approval(
            suggestion_id="sug-1", suggestion_type="split"
        )

        # Act
        _ = await manager.approve_suggestion(suggestion_id="sug-1")

        # Assert
        approval = list(manager.approvals.values())[0]
        assert approval.approved_at is not None
        assert approval.user_comment is None


class TestRejectSuggestion:
    """Test rejecting suggestions."""

    @pytest.mark.asyncio
    async def test_reject_existing_suggestion(self, memory_bank_dir: Path):
        """Test rejecting an existing suggestion."""
        # Arrange
        manager = ApprovalManager(memory_bank_dir=memory_bank_dir)
        _ = await manager.request_approval(
            suggestion_id="sug-1", suggestion_type="reorganization"
        )

        # Act
        result = await manager.reject_suggestion(
            suggestion_id="sug-1", user_comment="Not needed"
        )

        # Assert
        assert result["status"] == "rejected"
        approval = list(manager.approvals.values())[0]
        assert approval.user_comment == "Not needed"

    @pytest.mark.asyncio
    async def test_reject_nonexistent_suggestion_returns_error(
        self, memory_bank_dir: Path
    ):
        """Test rejecting nonexistent suggestion returns error."""
        # Arrange
        manager = ApprovalManager(memory_bank_dir=memory_bank_dir)

        # Act
        result = await manager.reject_suggestion(suggestion_id="nonexistent")

        # Assert
        assert result["status"] == "error"
        message = cast(str, result["message"])
        assert "No approval found" in message


class TestMarkAsApplied:
    """Test marking approvals as applied."""

    @pytest.mark.asyncio
    async def test_mark_approval_as_applied(self, memory_bank_dir: Path):
        """Test marking approval as applied."""
        # Arrange
        manager = ApprovalManager(memory_bank_dir=memory_bank_dir)
        approval_result = await manager.request_approval(
            suggestion_id="sug-1", suggestion_type="consolidation"
        )
        approval_id = cast(str, approval_result["approval_id"])

        # Act
        result = await manager.mark_as_applied(
            approval_id=approval_id, execution_id="exec-1"
        )

        # Assert
        assert result["status"] == "applied"
        assert result["execution_id"] == "exec-1"
        approval = manager.approvals[approval_id]
        assert approval.status == ApprovalStatus.APPLIED.value
        assert approval.execution_id == "exec-1"

    @pytest.mark.asyncio
    async def test_mark_nonexistent_approval_returns_error(self, memory_bank_dir: Path):
        """Test marking nonexistent approval returns error."""
        # Arrange
        manager = ApprovalManager(memory_bank_dir=memory_bank_dir)

        # Act
        result = await manager.mark_as_applied(
            approval_id="nonexistent", execution_id="exec-1"
        )

        # Assert
        assert result["status"] == "error"


class TestPreferenceManagement:
    """Test preference management."""

    @pytest.mark.asyncio
    async def test_add_preference(self, memory_bank_dir: Path):
        """Test adding auto-approval preference."""
        # Arrange
        manager = ApprovalManager(memory_bank_dir=memory_bank_dir)

        # Act
        result = await manager.add_preference(
            pattern_type="consolidation",
            auto_approve=True,
            conditions={"min_confidence": 0.8},
        )

        # Assert
        assert result["status"] == "success"
        assert len(manager.preferences) == 1
        assert manager.preferences[0].pattern_type == "consolidation"

    @pytest.mark.asyncio
    async def test_add_preference_replaces_existing(self, memory_bank_dir: Path):
        """Test adding preference replaces existing one."""
        # Arrange
        manager = ApprovalManager(memory_bank_dir=memory_bank_dir)
        _ = await manager.add_preference(pattern_type="split", auto_approve=True)

        # Act
        _ = await manager.add_preference(pattern_type="split", auto_approve=False)

        # Assert
        assert len(manager.preferences) == 1
        assert manager.preferences[0].auto_approve is False

    @pytest.mark.asyncio
    async def test_remove_preference(self, memory_bank_dir: Path):
        """Test removing preference."""
        # Arrange
        manager = ApprovalManager(memory_bank_dir=memory_bank_dir)
        _ = await manager.add_preference(
            pattern_type="consolidation", auto_approve=True
        )

        # Act
        result = await manager.remove_preference(pattern_type="consolidation")

        # Assert
        assert result["status"] == "success"
        assert len(manager.preferences) == 0

    @pytest.mark.asyncio
    async def test_remove_nonexistent_preference(self, memory_bank_dir: Path):
        """Test removing nonexistent preference."""
        # Arrange
        manager = ApprovalManager(memory_bank_dir=memory_bank_dir)

        # Act
        result = await manager.remove_preference(pattern_type="nonexistent")

        # Assert
        assert result["status"] == "not_found"

    @pytest.mark.asyncio
    async def test_get_preferences(self, memory_bank_dir: Path):
        """Test getting all preferences."""
        # Arrange
        manager = ApprovalManager(memory_bank_dir=memory_bank_dir)
        _ = await manager.add_preference(
            pattern_type="consolidation", auto_approve=True
        )
        _ = await manager.add_preference(pattern_type="split", auto_approve=False)

        # Act
        result = await manager.get_preferences()

        # Assert
        assert result["count"] == 2
        preferences_raw: object | None = result.get("preferences")
        preferences: list[object] | None = (
            cast(list[object] | None, preferences_raw)
            if isinstance(preferences_raw, list)
            else None
        )
        assert isinstance(preferences, list)
        assert len(preferences) == 2


class TestApprovalQueries:
    """Test approval query methods."""

    @pytest.mark.asyncio
    async def test_get_approval_by_id(self, memory_bank_dir: Path):
        """Test retrieving approval by ID."""
        # Arrange
        manager = ApprovalManager(memory_bank_dir=memory_bank_dir)
        approval_result = await manager.request_approval(
            suggestion_id="sug-1", suggestion_type="consolidation"
        )
        approval_id_raw = approval_result.get("approval_id")
        assert isinstance(approval_id_raw, str)
        approval_id: str = approval_id_raw

        # Act
        result = await manager.get_approval(approval_id)

        # Assert
        assert result is not None
        assert result["approval_id"] == approval_id

    @pytest.mark.asyncio
    async def test_get_approvals_for_suggestion(self, memory_bank_dir: Path):
        """Test getting all approvals for a suggestion."""
        # Arrange
        manager = ApprovalManager(memory_bank_dir=memory_bank_dir)
        _ = await manager.request_approval(
            suggestion_id="sug-1", suggestion_type="consolidation"
        )
        _ = await manager.request_approval(
            suggestion_id="sug-1", suggestion_type="consolidation"
        )

        # Act
        result = await manager.get_approvals_for_suggestion("sug-1")

        # Assert
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_get_pending_approvals(self, memory_bank_dir: Path):
        """Test getting all pending approvals."""
        # Arrange
        manager = ApprovalManager(memory_bank_dir=memory_bank_dir)
        _ = await manager.request_approval(
            suggestion_id="sug-1", suggestion_type="consolidation"
        )
        _ = await manager.request_approval(
            suggestion_id="sug-2", suggestion_type="split"
        )
        _ = await manager.approve_suggestion("sug-1")

        # Act
        result = await manager.get_pending_approvals()

        # Assert
        assert result["count"] == 1
        pending_approvals_raw: object | None = result.get("pending_approvals")
        pending_approvals: list[object] | None = (
            cast(list[object] | None, pending_approvals_raw)
            if isinstance(pending_approvals_raw, list)
            else None
        )
        assert isinstance(pending_approvals, list)
        assert len(pending_approvals) > 0
        first_approval: dict[str, object] = cast(
            dict[str, object], pending_approvals[0]
        )
        assert isinstance(first_approval, dict)
        suggestion_id: object | None = first_approval.get("suggestion_id")
        assert isinstance(suggestion_id, str)
        assert suggestion_id == "sug-2"


class TestApprovalHistory:
    """Test approval history functionality."""

    @pytest.mark.asyncio
    async def test_get_approval_history_filters_by_time(self, memory_bank_dir: Path):
        """Test history filtering by time range."""
        # Arrange
        manager = ApprovalManager(memory_bank_dir=memory_bank_dir)

        # Create old approval manually
        old_date = (datetime.now() - timedelta(days=100)).isoformat()
        old_approval = Approval(
            approval_id="old",
            suggestion_id="sug-old",
            suggestion_type="consolidation",
            status="approved",
            created_at=old_date,
        )
        manager.approvals["old"] = old_approval

        # Create new approval
        _ = await manager.request_approval(
            suggestion_id="sug-new", suggestion_type="split"
        )

        # Act
        result = await manager.get_approval_history(time_range_days=90)

        # Assert
        assert result["total_approvals"] == 1

    @pytest.mark.asyncio
    async def test_get_approval_history_calculates_statistics(
        self, memory_bank_dir: Path
    ):
        """Test history includes statistics."""
        # Arrange
        manager = ApprovalManager(memory_bank_dir=memory_bank_dir)
        _ = await manager.request_approval(
            suggestion_id="sug-1", suggestion_type="consolidation"
        )
        _ = await manager.approve_suggestion("sug-1")

        _ = await manager.request_approval(
            suggestion_id="sug-2", suggestion_type="split"
        )
        _ = await manager.reject_suggestion("sug-2")

        # Act
        result = await manager.get_approval_history()

        # Assert
        assert result["total_approvals"] == 2
        assert result["approved"] == 1
        assert result["rejected"] == 1
        assert result["approval_rate"] == 0.5


class TestCleanupExpiredApprovals:
    """Test cleanup of expired approvals."""

    @pytest.mark.asyncio
    async def test_cleanup_expires_old_pending_approvals(self, memory_bank_dir: Path):
        """Test cleanup expires old pending approvals."""
        # Arrange
        manager = ApprovalManager(memory_bank_dir=memory_bank_dir)

        # Create old pending approval
        old_date = (datetime.now() - timedelta(days=40)).isoformat()
        old_approval = Approval(
            approval_id="old",
            suggestion_id="sug-old",
            suggestion_type="consolidation",
            status="pending",
            created_at=old_date,
        )
        manager.approvals["old"] = old_approval

        # Act
        result = await manager.cleanup_expired_approvals(expiry_days=30)

        # Assert
        assert result["expired_count"] == 1
        assert manager.approvals["old"].status == ApprovalStatus.EXPIRED.value

    @pytest.mark.asyncio
    async def test_cleanup_does_not_expire_approved_approvals(
        self, memory_bank_dir: Path
    ):
        """Test cleanup doesn't expire approved approvals."""
        # Arrange
        manager = ApprovalManager(memory_bank_dir=memory_bank_dir)

        # Create old approved approval
        old_date = (datetime.now() - timedelta(days=40)).isoformat()
        old_approval = Approval(
            approval_id="old",
            suggestion_id="sug-old",
            suggestion_type="consolidation",
            status="approved",
            created_at=old_date,
        )
        manager.approvals["old"] = old_approval

        # Act
        result = await manager.cleanup_expired_approvals(expiry_days=30)

        # Assert
        assert result["expired_count"] == 0
        assert manager.approvals["old"].status == "approved"
