"""Unit tests for OperationStatus enum and JSON serialization."""

from __future__ import annotations

from cortex.core.models import OperationStatus, SubmoduleInitResult


class TestOperationStatusEnum:
    """Test OperationStatus enum definition and values."""

    def test_enum_has_exactly_two_members(self) -> None:
        """OperationStatus must have exactly SUCCESS and ERROR."""
        assert len(OperationStatus) == 2
        assert set(OperationStatus) == {OperationStatus.SUCCESS, OperationStatus.ERROR}

    def test_success_value(self) -> None:
        """SUCCESS serializes to string 'success'."""
        assert OperationStatus.SUCCESS.value == "success"

    def test_error_value(self) -> None:
        """ERROR serializes to string 'error'."""
        assert OperationStatus.ERROR.value == "error"

    def test_equality_with_string(self) -> None:
        """Enum compares equal to its string value for backward compatibility."""
        assert OperationStatus.SUCCESS == "success"
        assert OperationStatus.ERROR == "error"


class TestOperationStatusPydanticSerialization:
    """Test that Pydantic models using OperationStatus serialize to JSON strings."""

    def test_submodule_init_result_serializes_success(self) -> None:
        """SubmoduleInitResult with status SUCCESS serializes to "success" in JSON."""
        result = SubmoduleInitResult(status=OperationStatus.SUCCESS, action="init")
        data = result.model_dump(mode="json")
        assert data["status"] == "success"

    def test_submodule_init_result_serializes_error(self) -> None:
        """SubmoduleInitResult with status ERROR serializes to "error" in JSON."""
        result = SubmoduleInitResult(
            status=OperationStatus.ERROR, error="Something failed"
        )
        data = result.model_dump(mode="json")
        assert data["status"] == "error"

    def test_submodule_init_result_from_json(self) -> None:
        """JSON with string status is parsed and coerced to enum."""
        json_str = '{"status": "success", "action": "init"}'
        result = SubmoduleInitResult.model_validate_json(json_str)
        assert result.status == OperationStatus.SUCCESS
        assert result.status == "success"
