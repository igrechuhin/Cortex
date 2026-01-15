"""
Unit tests for main.py error handling.

Tests the comprehensive error handling for MCP server connection issues,
including BaseExceptionGroup, anyio.BrokenResourceError, and other
connection-related exceptions.
"""

from builtins import BaseExceptionGroup
from unittest.mock import MagicMock, patch

import anyio
import pytest

from cortex.main import main


class TestMainErrorHandling:
    """Tests for main() error handling paths."""

    @patch("cortex.main.mcp")
    def test_keyboard_interrupt_handling(self, mock_mcp: MagicMock) -> None:
        """Test that KeyboardInterrupt is handled gracefully."""
        # Arrange
        mock_mcp.run.side_effect = KeyboardInterrupt()

        # Act
        with pytest.raises(SystemExit) as exc_info:
            main()

        # Assert
        assert exc_info.value.code == 0
        mock_mcp.run.assert_called_once_with(transport="stdio")

    @patch("cortex.main.mcp")
    def test_broken_pipe_error_handling(self, mock_mcp: MagicMock) -> None:
        """Test that BrokenPipeError is handled gracefully."""
        # Arrange
        mock_mcp.run.side_effect = BrokenPipeError("Broken pipe")

        # Act
        with pytest.raises(SystemExit) as exc_info:
            main()

        # Assert
        assert exc_info.value.code == 0
        mock_mcp.run.assert_called_once_with(transport="stdio")

    @patch("cortex.main.mcp")
    def test_anyio_broken_resource_error_handling(self, mock_mcp: MagicMock) -> None:
        """Test that anyio.BrokenResourceError is handled gracefully."""
        # Arrange
        mock_mcp.run.side_effect = anyio.BrokenResourceError("Resource broken")

        # Act
        with pytest.raises(SystemExit) as exc_info:
            main()

        # Assert
        assert exc_info.value.code == 0
        mock_mcp.run.assert_called_once_with(transport="stdio")

    @patch("cortex.main.mcp")
    def test_base_exception_group_with_broken_resource_error(
        self, mock_mcp: MagicMock
    ) -> None:
        """Test that BaseExceptionGroup containing BrokenResourceError is handled gracefully."""
        # Arrange
        broken_resource_error = anyio.BrokenResourceError("Resource broken")
        exception_group = BaseExceptionGroup(
            "unhandled errors in a TaskGroup", [broken_resource_error]
        )
        mock_mcp.run.side_effect = exception_group

        # Act
        with pytest.raises(SystemExit) as exc_info:
            main()

        # Assert
        assert exc_info.value.code == 0
        mock_mcp.run.assert_called_once_with(transport="stdio")

    @patch("cortex.main.mcp")
    def test_base_exception_group_with_other_exceptions(
        self, mock_mcp: MagicMock
    ) -> None:
        """Test that BaseExceptionGroup with non-connection errors exits with code 1."""
        # Arrange
        other_error = ValueError("Some other error")
        exception_group = BaseExceptionGroup(
            "unhandled errors in a TaskGroup", [other_error]
        )
        mock_mcp.run.side_effect = exception_group

        # Act
        with pytest.raises(SystemExit) as exc_info:
            main()

        # Assert
        assert exc_info.value.code == 1
        mock_mcp.run.assert_called_once_with(transport="stdio")

    @patch("cortex.main.mcp")
    def test_base_exception_group_with_mixed_exceptions(
        self, mock_mcp: MagicMock
    ) -> None:
        """Test that BaseExceptionGroup with BrokenResourceError exits gracefully even with other exceptions."""
        # Arrange
        broken_resource_error = anyio.BrokenResourceError("Resource broken")
        other_error = ValueError("Some other error")
        exception_group = BaseExceptionGroup(
            "unhandled errors in a TaskGroup", [broken_resource_error, other_error]
        )
        mock_mcp.run.side_effect = exception_group

        # Act
        with pytest.raises(SystemExit) as exc_info:
            main()

        # Assert
        assert (
            exc_info.value.code == 0
        )  # Should exit gracefully if BrokenResourceError found
        mock_mcp.run.assert_called_once_with(transport="stdio")

    @patch("cortex.main.mcp")
    def test_connection_error_handling(self, mock_mcp: MagicMock) -> None:
        """Test that ConnectionError exits with code 1."""
        # Arrange
        mock_mcp.run.side_effect = ConnectionError("Connection failed")

        # Act
        with pytest.raises(SystemExit) as exc_info:
            main()

        # Assert
        assert exc_info.value.code == 1
        mock_mcp.run.assert_called_once_with(transport="stdio")

    @patch("cortex.main.mcp")
    def test_oserror_broken_pipe_handling(self, mock_mcp: MagicMock) -> None:
        """Test that OSError with 'Broken pipe' message exits gracefully."""
        # Arrange
        mock_mcp.run.side_effect = OSError("Broken pipe")

        # Act
        with pytest.raises(SystemExit) as exc_info:
            main()

        # Assert
        assert exc_info.value.code == 0
        mock_mcp.run.assert_called_once_with(transport="stdio")

    @patch("cortex.main.mcp")
    def test_oserror_connection_reset_handling(self, mock_mcp: MagicMock) -> None:
        """Test that OSError with 'Connection reset' message exits gracefully."""
        # Arrange
        mock_mcp.run.side_effect = OSError("Connection reset by peer")

        # Act
        with pytest.raises(SystemExit) as exc_info:
            main()

        # Assert
        assert exc_info.value.code == 0
        mock_mcp.run.assert_called_once_with(transport="stdio")

    @patch("cortex.main.mcp")
    def test_oserror_other_handling(self, mock_mcp: MagicMock) -> None:
        """Test that other OSError exits with code 1."""
        # Arrange
        mock_mcp.run.side_effect = OSError("Permission denied")

        # Act
        with pytest.raises(SystemExit) as exc_info:
            main()

        # Assert
        assert exc_info.value.code == 1
        mock_mcp.run.assert_called_once_with(transport="stdio")

    @patch("cortex.main.mcp")
    def test_unexpected_exception_handling(self, mock_mcp: MagicMock) -> None:
        """Test that unexpected exceptions exit with code 1."""
        # Arrange
        mock_mcp.run.side_effect = ValueError("Unexpected error")

        # Act
        with pytest.raises(SystemExit) as exc_info:
            main()

        # Assert
        assert exc_info.value.code == 1
        mock_mcp.run.assert_called_once_with(transport="stdio")


class TestMCPStabilityConnectionErrorDetection:
    """Tests for _is_connection_error() in mcp_stability.py."""

    def test_broken_resource_error_is_connection_error(self) -> None:
        """Test that anyio.BrokenResourceError is recognized as connection error."""
        # Arrange
        from cortex.core.mcp_stability import _is_connection_error

        error = anyio.BrokenResourceError("Resource broken")

        # Act
        result = _is_connection_error(error)

        # Assert
        assert result is True

    def test_connection_error_is_connection_error(self) -> None:
        """Test that ConnectionError is recognized as connection error."""
        # Arrange
        from cortex.core.mcp_stability import _is_connection_error

        error = ConnectionError("Connection failed")

        # Act
        result = _is_connection_error(error)

        # Assert
        assert result is True

    def test_broken_pipe_error_is_connection_error(self) -> None:
        """Test that BrokenPipeError is recognized as connection error."""
        # Arrange
        from cortex.core.mcp_stability import _is_connection_error

        error = BrokenPipeError("Broken pipe")

        # Act
        result = _is_connection_error(error)

        # Assert
        assert result is True

    def test_oserror_is_connection_error(self) -> None:
        """Test that OSError is recognized as connection error."""
        # Arrange
        from cortex.core.mcp_stability import _is_connection_error

        error = OSError("OS error")

        # Act
        result = _is_connection_error(error)

        # Assert
        assert result is True

    def test_runtime_error_is_connection_error(self) -> None:
        """Test that RuntimeError is recognized as connection error."""
        # Arrange
        from cortex.core.mcp_stability import _is_connection_error

        error = RuntimeError("Runtime error")

        # Act
        result = _is_connection_error(error)

        # Assert
        assert result is True

    def test_value_error_is_not_connection_error(self) -> None:
        """Test that ValueError is not recognized as connection error."""
        # Arrange
        from cortex.core.mcp_stability import _is_connection_error

        error = ValueError("Value error")

        # Act
        result = _is_connection_error(error)

        # Assert
        assert result is False
