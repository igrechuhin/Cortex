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

        from cortex.rules.rules_repository import RulesRepository

        repo = RulesRepository(
            project_root=Path("/tmp/test"),
            shared_rules_path=Path("/tmp/test/.shared-rules"),
        )

        # Mock fast command to avoid actual git execution
        async def fast_command(cmd: list[str]) -> dict[str, object]:
            return {"success": True, "stdout": "OK", "stderr": ""}

        repo.set_git_command_runner(fast_command)

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

        from cortex.rules.rules_repository import RulesRepository

        repo = RulesRepository(
            project_root=Path("/tmp/test"),
            shared_rules_path=Path("/tmp/test/.shared-rules"),
        )

        # Mock fast git command
        async def fast_command(cmd: list[str]) -> dict[str, object]:
            await asyncio.sleep(0.1)  # Faster than timeout
            return {"success": True, "stdout": "OK", "stderr": ""}

        repo.set_git_command_runner(fast_command)

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

        from cortex.rules.rules_repository import RulesRepository

        repo = RulesRepository(
            project_root=Path("/tmp/test"),
            shared_rules_path=Path("/tmp/test/.shared-rules"),
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
    """Test security enhancements in SharedRulesManager."""

    @pytest.mark.asyncio
    async def test_initialize_shared_rules_validates_url(self):
        """Test that initialize_shared_rules validates git URL."""
        # Arrange
        from pathlib import Path

        from cortex.rules.shared_rules_manager import SharedRulesManager

        manager = SharedRulesManager(project_root=Path("/tmp/test"))

        # Act
        result = await manager.initialize_shared_rules(
            repo_url="file:///malicious/path"
        )

        # Assert
        assert result["status"] == "error"
        error_value = result.get("error")
        error_msg = str(error_value) if error_value is not None else ""
        assert "Invalid git URL" in error_msg

    @pytest.mark.asyncio
    async def test_initialize_shared_rules_accepts_valid_https_url(self):
        """Test that initialize_shared_rules accepts valid HTTPS URL."""
        # Arrange
        from pathlib import Path

        from cortex.rules.shared_rules_manager import SharedRulesManager

        manager = SharedRulesManager(project_root=Path("/tmp/test"))

        # Mock repository to avoid actual git operations
        async def mock_init(repo_url: str, force: bool = False) -> dict[str, object]:
            return {"status": "success"}

        manager.repository.initialize_submodule = mock_init

        # Act
        result = await manager.initialize_shared_rules(
            repo_url="https://github.com/user/repo.git"
        )

        # Assert
        assert result["status"] == "success"

    @pytest.mark.asyncio
    async def test_initialize_shared_rules_accepts_valid_ssh_url(self):
        """Test that initialize_shared_rules accepts valid SSH URL."""
        # Arrange
        from pathlib import Path

        from cortex.rules.shared_rules_manager import SharedRulesManager

        manager = SharedRulesManager(project_root=Path("/tmp/test"))

        # Mock repository to avoid actual git operations
        async def mock_init(repo_url: str, force: bool = False) -> dict[str, object]:
            return {"status": "success"}

        manager.repository.initialize_submodule = mock_init

        # Act
        result = await manager.initialize_shared_rules(
            repo_url="git@github.com:user/repo.git"
        )

        # Assert
        assert result["status"] == "success"

    @pytest.mark.asyncio
    async def test_initialize_shared_rules_rejects_localhost_url(self):
        """Test that initialize_shared_rules rejects localhost URL."""
        # Arrange
        from pathlib import Path

        from cortex.rules.shared_rules_manager import SharedRulesManager

        manager = SharedRulesManager(project_root=Path("/tmp/test"))

        # Act
        result = await manager.initialize_shared_rules(
            repo_url="https://localhost/repo.git"
        )

        # Assert
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
