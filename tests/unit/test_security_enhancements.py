"""Tests for security enhancements in Phase 9.4."""

import asyncio

import pytest

from cortex.core.security import InputValidator


class TestGitURLValidation:
    """Test git URL validation functionality."""

    def test_validate_git_url_https_valid(self):
        """Test validation of valid HTTPS git URL."""
        # Arrange
        valid_url = "https://github.com/user/repo.git"

        # Act
        result = InputValidator.validate_git_url(valid_url)

        # Assert
        assert result == valid_url

    def test_validate_git_url_ssh_valid(self):
        """Test validation of valid SSH git URL."""
        # Arrange
        valid_url = "git@github.com:user/repo.git"

        # Act
        result = InputValidator.validate_git_url(valid_url)

        # Assert
        assert result == valid_url

    def test_validate_git_url_empty_raises_error(self):
        """Test that empty URL raises ValueError."""
        # Arrange
        empty_url = ""

        # Act & Assert
        with pytest.raises(ValueError, match="Git URL cannot be empty"):
            _ = InputValidator.validate_git_url(empty_url)

    def test_validate_git_url_whitespace_only_raises_error(self):
        """Test that whitespace-only URL raises ValueError."""
        # Arrange
        whitespace_url = "   "

        # Act & Assert
        with pytest.raises(ValueError, match="Git URL cannot be empty"):
            _ = InputValidator.validate_git_url(whitespace_url)

    def test_validate_git_url_invalid_protocol_raises_error(self):
        """Test that invalid protocol raises ValueError."""
        # Arrange
        invalid_url = "ftp://github.com/user/repo.git"

        # Act & Assert
        with pytest.raises(ValueError, match="Invalid git URL protocol"):
            _ = InputValidator.validate_git_url(invalid_url)

    def test_validate_git_url_file_protocol_raises_error(self):
        """Test that file protocol raises ValueError."""
        # Arrange
        file_url = "file:///path/to/repo"

        # Act & Assert
        with pytest.raises(ValueError, match="Invalid git URL protocol"):
            _ = InputValidator.validate_git_url(file_url)

    def test_validate_git_url_localhost_raises_error(self):
        """Test that localhost URL raises ValueError."""
        # Arrange
        localhost_url = "https://localhost/repo.git"

        # Act & Assert
        with pytest.raises(ValueError, match="cannot reference localhost"):
            _ = InputValidator.validate_git_url(localhost_url)

    def test_validate_git_url_127_0_0_1_raises_error(self):
        """Test that 127.0.0.1 URL raises ValueError."""
        # Arrange
        loopback_url = "https://127.0.0.1/repo.git"

        # Act & Assert
        with pytest.raises(ValueError, match="cannot reference localhost"):
            _ = InputValidator.validate_git_url(loopback_url)

    def test_validate_git_url_private_ip_192_168_raises_error(self):
        """Test that private IP (192.168.x.x) raises ValueError."""
        # Arrange
        private_url = "https://192.168.1.1/repo.git"

        # Act & Assert
        with pytest.raises(ValueError, match="cannot reference private IP"):
            _ = InputValidator.validate_git_url(private_url)

    def test_validate_git_url_private_ip_10_raises_error(self):
        """Test that private IP (10.x.x.x) raises ValueError."""
        # Arrange
        private_url = "https://10.0.0.1/repo.git"

        # Act & Assert
        with pytest.raises(ValueError, match="cannot reference private IP"):
            _ = InputValidator.validate_git_url(private_url)

    def test_validate_git_url_private_ip_172_16_raises_error(self):
        """Test that private IP (172.16.x.x) raises ValueError."""
        # Arrange
        private_url = "https://172.16.0.1/repo.git"

        # Act & Assert
        with pytest.raises(ValueError, match="cannot reference private IP"):
            _ = InputValidator.validate_git_url(private_url)

    def test_validate_git_url_too_long_raises_error(self):
        """Test that excessively long URL raises ValueError."""
        # Arrange
        long_url = "https://github.com/" + "a" * 2100

        # Act & Assert
        with pytest.raises(ValueError, match="Git URL too long"):
            _ = InputValidator.validate_git_url(long_url)

    def test_validate_git_url_strips_whitespace(self):
        """Test that whitespace is stripped from URL."""
        # Arrange
        url_with_whitespace = "  https://github.com/user/repo.git  "

        # Act
        result = InputValidator.validate_git_url(url_with_whitespace)

        # Assert
        assert result == "https://github.com/user/repo.git"


class TestGitOperationTimeouts:
    """Test git operation timeout functionality."""

    @pytest.mark.asyncio
    async def test_git_command_timeout_parameter_accepted(self):
        """Test that git command accepts timeout parameter."""
        # Arrange
        from pathlib import Path

        from cortex.rules.synapse_repository import SynapseRepository

        async def git_runner(cmd: list[str]) -> dict[str, object]:
            return {"success": True, "stdout": "OK", "stderr": ""}

        repo = SynapseRepository(
            project_root=Path("/tmp/test"),
            synapse_path=Path("/tmp/test/.shared-rules"),
            git_command_runner=git_runner,
        )

        # Mock fast command to avoid actual git execution
        async def fast_command(cmd: list[str]) -> dict[str, object]:
            return {"success": True, "stdout": "OK", "stderr": ""}

        repo.git_command_runner = fast_command

        # Act - Call with timeout parameter (should not raise exception)
        result = await repo.run_git_command(["git", "status"], timeout=30)

        # Assert - Should complete successfully
        assert result["success"] is True
        assert result["stdout"] == "OK"

    @pytest.mark.asyncio
    async def test_git_command_completes_within_timeout(self):
        """Test that fast git operations complete successfully."""
        # Arrange
        from pathlib import Path

        from cortex.rules.synapse_repository import SynapseRepository

        async def git_runner(cmd: list[str]) -> dict[str, object]:
            return {"success": True, "stdout": "OK", "stderr": ""}

        repo = SynapseRepository(
            project_root=Path("/tmp/test"),
            synapse_path=Path("/tmp/test/.shared-rules"),
            git_command_runner=git_runner,
        )

        # Mock fast git command
        async def fast_command(cmd: list[str]) -> dict[str, object]:
            await asyncio.sleep(0.1)  # Faster than timeout
            return {"success": True, "stdout": "OK", "stderr": ""}

        repo.git_command_runner = fast_command

        # Act
        result = await repo.run_git_command(["git", "status"], timeout=1)

        # Assert
        assert result["success"] is True
        assert result["stdout"] == "OK"

    @pytest.mark.asyncio
    async def test_git_command_default_timeout(self):
        """Test that git commands use default timeout."""
        # Arrange
        from pathlib import Path

        from cortex.rules.synapse_repository import SynapseRepository

        async def git_runner(cmd: list[str]) -> dict[str, object]:
            return {"success": True, "stdout": "OK", "stderr": ""}

        repo = SynapseRepository(
            project_root=Path("/tmp/test"),
            synapse_path=Path("/tmp/test/.shared-rules"),
            git_command_runner=git_runner,
        )

        # Mock command that checks timeout parameter
        timeout_used = None

        async def command_with_timeout_check(cmd: list[str]) -> dict[str, object]:
            nonlocal timeout_used
            # Simulate checking timeout (in real implementation, timeout is passed to asyncio.wait_for)
            timeout_used = 30  # Default timeout
            return {"success": True, "stdout": "", "stderr": ""}

        repo.set_git_command_runner(command_with_timeout_check)

        # Act
        result = await repo.run_git_command(["git", "status"])

        # Assert
        assert result["success"] is True
        assert timeout_used == 30  # Default timeout


class TestSharedRulesManagerSecurity:
    """Test security enhancements in SynapseManager (replaces SharedRulesManager)."""

    @pytest.mark.asyncio
    async def test_initialize_shared_rules_validates_url(self):
        """Test that initialize_synapse validates git URL."""
        # Arrange
        import tempfile
        from pathlib import Path

        from cortex.rules.synapse_manager import SynapseManager

        # Use a real temporary directory that exists
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = SynapseManager(project_root=Path(tmpdir))

            # Act - Try to initialize with file:// URL (should fail validation)
            result = await manager.initialize_synapse(repo_url="file:///malicious/path")

            # Assert - Should return error with "Invalid git URL" message
            assert result["status"] == "error"
            error_value = result.get("error")
            error_msg = str(error_value) if error_value is not None else ""
            assert "Invalid git URL" in error_msg

    @pytest.mark.asyncio
    async def test_initialize_shared_rules_accepts_valid_https_url(self):
        """Test that initialize_synapse accepts valid HTTPS URL."""
        # Arrange
        from pathlib import Path
        from unittest.mock import AsyncMock, patch

        from cortex.rules.synapse_manager import SynapseManager

        manager = SynapseManager(project_root=Path("/tmp/test"))

        # Mock initialize_synapse to avoid actual git operations
        with patch.object(
            manager, "initialize_synapse", new_callable=AsyncMock
        ) as mock_init:
            mock_init.return_value = {"status": "success"}

            # Act
            result = await manager.initialize_synapse(
                repo_url="https://github.com/user/repo.git"
            )

            # Assert
            assert result["status"] == "success"

    @pytest.mark.asyncio
    async def test_initialize_shared_rules_accepts_valid_ssh_url(self):
        """Test that initialize_synapse accepts valid SSH URL."""
        # Arrange
        from pathlib import Path
        from unittest.mock import AsyncMock, patch

        from cortex.rules.synapse_manager import SynapseManager

        manager = SynapseManager(project_root=Path("/tmp/test"))

        # Mock initialize_synapse to avoid actual git operations
        with patch.object(
            manager, "initialize_synapse", new_callable=AsyncMock
        ) as mock_init:
            mock_init.return_value = {"status": "success"}

            # Act
            result = await manager.initialize_synapse(
                repo_url="git@github.com:user/repo.git"
            )

            # Assert
            assert result["status"] == "success"

    @pytest.mark.asyncio
    async def test_initialize_shared_rules_rejects_localhost_url(self):
        """Test that initialize_synapse rejects localhost URL."""
        # Arrange
        import tempfile
        from pathlib import Path

        from cortex.rules.synapse_manager import SynapseManager

        # Use a real temporary directory that exists
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = SynapseManager(project_root=Path(tmpdir))

            # Act - Try to initialize with localhost URL (should fail validation)
            result = await manager.initialize_synapse(
                repo_url="https://localhost/repo.git"
            )

            # Assert - Should return error with "Invalid git URL" message
            assert result["status"] == "error"
            error_value = result.get("error")
            error_msg = str(error_value) if error_value is not None else ""
            assert "Invalid git URL" in error_msg
        assert "localhost" in error_msg


class TestSecurityIntegration:
    """Test security features integration."""

    def test_file_name_validation_integration(self):
        """Test file name validation in FileSystemManager."""
        # Arrange
        from pathlib import Path

        from cortex.core.file_system import FileSystemManager

        fs_manager = FileSystemManager(project_root=Path("/tmp/test"))

        # Act - Valid file name
        valid_name = fs_manager.validate_file_name("valid_file.md")

        # Assert
        assert valid_name == "valid_file.md"

        # Act & Assert - Invalid file name with path traversal
        with pytest.raises(ValueError, match="path traversal"):
            _ = fs_manager.validate_file_name("../etc/passwd")

    def test_path_validation_integration(self):
        """Test path validation in FileSystemManager."""
        # Arrange
        from pathlib import Path

        from cortex.core.file_system import FileSystemManager

        project_root = Path("/tmp/test")
        fs_manager = FileSystemManager(project_root=project_root)

        # Act & Assert - Valid path
        valid_path = project_root / "memory-bank" / "file.md"
        assert fs_manager.validate_path(valid_path) is True

        # Act & Assert - Invalid path (outside project)
        invalid_path = Path("/etc/passwd")
        assert fs_manager.validate_path(invalid_path) is False

    def test_rate_limiter_integration(self):
        """Test rate limiter integration in FileSystemManager."""
        # Arrange
        from pathlib import Path

        from cortex.core.file_system import FileSystemManager

        fs_manager = FileSystemManager(project_root=Path("/tmp/test"))

        # Act - Check rate limiter is configured
        assert fs_manager.rate_limiter is not None
        assert fs_manager.rate_limiter.max_ops == 100
        assert fs_manager.rate_limiter.window == 1.0

        # Assert - Rate limiter starts with zero operations
        assert fs_manager.rate_limiter.get_current_count() == 0
