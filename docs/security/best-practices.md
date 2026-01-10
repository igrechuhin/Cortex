# Security Best Practices

**Last Updated:** 2026-01-03
**Status:** Official Security Guidelines

---

## Overview

This document provides comprehensive security best practices for the Cortex project. All developers, contributors, and users should follow these guidelines to maintain the security posture of the system.

---

## Table of Contents

1. [MCP Security Model](#mcp-security-model)
2. [Input Validation](#input-validation)
3. [File Operations Security](#file-operations-security)
4. [Git Operations Security](#git-operations-security)
5. [Authentication & Authorization](#authentication--authorization)
6. [Data Protection](#data-protection)
7. [Network Security](#network-security)
8. [Dependency Management](#dependency-management)
9. [Logging & Monitoring](#logging--monitoring)
10. [Incident Response](#incident-response)
11. [Security Testing Guide](#security-testing-guide)
12. [Security Checklist](#security-checklist)

---

## MCP Security Model

### Security Model Overview

Cortex operates as a Model Context Protocol (MCP) server that provides structured memory management for AI assistants. Understanding the security model and trust boundaries is essential for secure deployment.

### Trust Boundaries

#### Layer 1: MCP Protocol Transport

- Communication over stdio (standard input/output)
- No network exposure by default
- Process-level isolation
- Inherited security context from parent process

#### Layer 2: Tool Authorization

- All tools are exposed to authorized MCP clients
- No per-tool authorization mechanism
- Trust model: Client is trusted to use tools appropriately
- Security relies on client-side validation and user consent

#### Layer 3: File System Sandbox

- All file operations restricted to `project_root`
- Path validation prevents directory traversal
- Symbolic link resolution enforced
- No access to files outside project boundaries

#### Layer 4: Resource Protection

- Rate limiting on file operations (100 ops/sec)
- File size limits (10 MB per file)
- Token budget enforcement (max 200,000 tokens)
- Concurrent operation limits (10 parallel operations)

### Security Assumptions

**Trusted:**

- ✅ MCP client (Claude Desktop, other MCP clients)
- ✅ Project root directory and its contents
- ✅ Shared rules repository (if configured)
- ✅ Local git configuration
- ✅ User-provided inputs (with validation)

**Untrusted:**

- ❌ External git repositories (URL validation required)
- ❌ File paths outside project root
- ❌ Symbolic links pointing outside project
- ❌ Network resources (if networking added)

### Threat Model

**Threats Mitigated:**

1. **Path Traversal Attacks** - Prevented by path validation and sandboxing
2. **Arbitrary File Access** - Prevented by project root enforcement
3. **Git URL Injection** - Prevented by URL validation and protocol restrictions
4. **Resource Exhaustion** - Mitigated by rate limiting and size limits
5. **Code Injection** - Prevented by avoiding shell execution with user input
6. **Symlink Attacks** - Mitigated by path resolution

**Residual Risks:**

1. **Malicious Project Contents** - Server operates on local files (assume trusted)
2. **Resource Exhaustion** - Large projects may consume significant resources
3. **Git Credential Exposure** - Inherits git credentials from system
4. **Local File Disclosure** - Client can read project files (by design)

### Security Controls

**Input Validation (Defense Layer 1):**

```python
from cortex.core.security import InputValidator

# File name validation
safe_name = InputValidator.validate_file_name(user_input)

# Path validation
InputValidator.validate_path(file_path, project_root)

# Git URL validation
safe_url = InputValidator.validate_git_url(repo_url)
```

**Sandboxing (Defense Layer 2):**

```python
from cortex.core.file_system import FileSystemManager

fs_manager = FileSystemManager(project_root)

# All operations automatically sandboxed
if not fs_manager.validate_path(file_path):
    raise PermissionError("Path outside project root")
```

**Rate Limiting (Defense Layer 3):**

```python
from cortex.core.security import RateLimiter

# Automatic rate limiting on file operations
await rate_limiter.acquire()  # Throttles at 100 ops/sec
```

### Deployment Security

**Development Environment:**

- Low risk: Single user, trusted project
- Minimal additional security needed
- Standard file permissions sufficient

**CI/CD Environment:**

- Medium risk: Automated execution, untrusted inputs
- Recommendations:
  - Run in isolated container
  - Read-only file system where possible
  - Restrict network access
  - Use dedicated service account

**Multi-User Server (Future):**

- High risk: Multiple users, shared resources
- Required enhancements:
  - Per-user authentication
  - Per-user authorization
  - Per-user rate limiting
  - Audit logging
  - Resource quotas

### Security Best Practices for Deployment

**Single-User CLI (Current):**

```bash
# Run with standard user permissions
cortex

# No additional security configuration needed
```

**Container Deployment:**

```dockerfile
# Use non-root user
USER node:node

# Read-only root filesystem
--read-only

# Drop all capabilities
--cap-drop=ALL

# Resource limits
--memory=512m --cpus=1.0
```

**Server Deployment (If Implemented):**

```bash
# Network isolation
--network=none

# User namespace isolation
--userns-remap=default

# AppArmor/SELinux profile
--security-opt apparmor=cortex
```

---

## Input Validation

### General Principles

- **Validate all external inputs** - Never trust user-provided data
- **Use whitelist validation** - Define what is allowed, not what is forbidden
- **Fail securely** - Invalid input should result in clear error messages
- **Sanitize before use** - Clean input data before processing

### File Name Validation

```python
from cortex.core.security import InputValidator

# Validate file names before use
try:
    safe_name = InputValidator.validate_file_name(user_input)
except ValueError as e:
    logger.warning(f"Invalid file name: {e}")
    return error_response("Invalid file name")
```

**Protected Against:**

- Path traversal (`..`, `/`, `\`)
- Invalid characters (`<>:"|?*\0`)
- Windows reserved names (CON, PRN, AUX, etc.)
- Names ending with period or space
- Excessively long names (>255 characters)

### Path Validation

```python
from pathlib import Path
from cortex.core.security import InputValidator

# Validate paths are within project boundaries
try:
    is_valid = InputValidator.validate_path(file_path, project_root)
except ValueError as e:
    logger.error(f"Path validation failed: {e}")
    return error_response("Invalid path")
```

**Protected Against:**

- Directory traversal attacks
- Access to files outside project root
- Symbolic link exploitation
- Absolute path injection

### Git URL Validation

```python
from cortex.core.security import InputValidator

# Validate git URLs before cloning
try:
    safe_url = InputValidator.validate_git_url(repo_url)
except ValueError as e:
    logger.warning(f"Invalid git URL: {e}")
    return error_response("Invalid repository URL")
```

**Protected Against:**

- Localhost/private IP access
- File protocol exploitation
- Malicious URL injection
- Protocol downgrade attacks

---

## File Operations Security

### Safe File Reading

```python
from cortex.core.file_system import FileSystemManager

fs_manager = FileSystemManager(project_root)

# Always validate paths before reading
if not fs_manager.validate_path(file_path):
    raise PermissionError(f"Path {file_path} is outside project root")

content, content_hash = await fs_manager.read_file(file_path)
```

**Security Features:**

- Path validation before access
- Rate limiting (100 ops/second)
- Content hashing for integrity
- Automatic lock management

### Safe File Writing

```python
# Write with conflict detection
try:
    new_hash = await fs_manager.write_file(
        file_path,
        content,
        expected_hash=current_hash  # Detect external modifications
    )
except FileConflictError as e:
    logger.warning(f"File conflict detected: {e}")
    # Handle conflict appropriately
```

**Security Features:**

- File locking prevents concurrent modifications
- Conflict detection via content hashing
- Git conflict marker detection
- Atomic write operations

### File Deletion

```python
# Validate before deletion
if not fs_manager.validate_path(file_path):
    raise PermissionError("Cannot delete files outside project")

if file_path.exists():
    file_path.unlink()  # Delete file
```

**Best Practices:**

- Always validate paths before deletion
- Log all deletion operations
- Consider implementing soft deletes
- Require confirmation for bulk deletions

---

## Git Operations Security

### Safe Git Command Execution

```python
from cortex.rules.rules_repository import RulesRepository

repo = RulesRepository(project_root, shared_rules_path)

# Git operations have built-in timeout
result = await repo.run_git_command(
    ["git", "clone", validated_url, local_path],
    timeout=30  # Prevent hanging operations
)

if not result["success"]:
    logger.error(f"Git operation failed: {result.get('error')}")
```

**Security Features:**

- Command injection prevention (no shell=True)
- Operation timeouts (30 seconds default)
- URL validation before cloning
- Working directory control

### Git Submodule Management

```python
# Initialize with validated URL
result = await shared_rules_manager.initialize_shared_rules(
    repo_url=validated_url,
    force=False
)

if result["status"] != "success":
    logger.error(f"Submodule initialization failed: {result.get('error')}")
```

**Best Practices:**

- Always validate git URLs
- Use HTTPS/SSH protocols only
- Avoid file:// protocol
- Set operation timeouts
- Log all git operations

---

## Authentication & Authorization

### Access Control

**Principle of Least Privilege:**

- Grant minimum necessary permissions
- Validate user permissions before operations
- Log all access attempts
- Implement role-based access control (RBAC)

### Session Management

**Best Practices:**

- Use secure session tokens
- Implement session timeouts
- Rotate session tokens regularly
- Invalidate sessions on logout

---

## Data Protection

### Sensitive Data Handling

**Never Log Sensitive Data:**

```python
from cortex.logging_config import get_logger

logger = get_logger(__name__)

# ✅ CORRECT - Sanitize sensitive data
user_data = {"email": "user@example.com", "password": "***"}
logger.info(f"User login attempt: {user_data}")

# ❌ WRONG - Logging passwords
logger.info(f"User password: {password}")  # NEVER DO THIS
```

**Sensitive Data Categories:**

- Passwords and credentials
- API keys and tokens
- Personal identifiable information (PII)
- Financial information
- Health records

### Data Encryption

**At Rest:**

- Use strong encryption algorithms (AES-256)
- Rotate encryption keys regularly
- Store keys securely (environment variables, key vaults)

**In Transit:**

- Use TLS 1.2 or higher
- Verify SSL certificates
- Implement certificate pinning for critical connections

---

## Network Security

### HTTP Client Configuration

**Secure Defaults:**

```python
import aiohttp
import ssl

# Create secure SSL context
ssl_context = ssl.create_default_context()
ssl_context.check_hostname = True
ssl_context.verify_mode = ssl.CERT_REQUIRED
ssl_context.minimum_version = ssl.TLSVersion.TLSv1_2

# Use secure connector
connector = aiohttp.TCPConnector(
    ssl=ssl_context,
    limit=100,
    limit_per_host=10
)
```

**Best Practices:**

- Always verify SSL certificates
- Use TLS 1.2 or higher
- Set connection timeouts
- Limit concurrent connections
- Validate response content types

### Rate Limiting

**Implementation:**

```python
from cortex.core.security import RateLimiter

rate_limiter = RateLimiter(max_ops=100, window_seconds=1.0)

# Acquire permission before operation
await rate_limiter.acquire()
```

**Configuration:**

The default rate limit is 100 operations per second, defined in `src/cortex/core/constants.py`:

```python
RATE_LIMIT_OPS_PER_SECOND = 100  # Rate limit for file operations
```

**Tuning Guidelines:**

- **Single-user CLI:** Default 100 ops/sec is sufficient
- **Multi-user server:** Consider reducing to 10-50 ops/sec per user
- **High-load scenarios:** Increase to 200-500 ops/sec with monitoring
- **Resource-constrained systems:** Reduce to 50 ops/sec

**Benefits:**

- Prevents abuse and DoS attacks
- Controls resource consumption
- Protects against brute force attacks
- Sliding window algorithm prevents burst abuse

---

## Dependency Management

### Vulnerability Scanning

**Regular Scans:**

```bash
# Scan for known vulnerabilities
pip-audit

# Alternative scanner
safety check

# Update dependencies with security fixes
uv lock --upgrade
```

**Best Practices:**

- Scan dependencies before deployment
- Update dependencies regularly
- Pin dependency versions
- Review security advisories
- Use trusted package sources

### Dependency Pinning

```toml
# pyproject.toml
dependencies = [
    "requests>=2.28.0,<3.0.0",  # Pin major versions
    "fastapi>=0.100.0,<1.0.0",
]
```

**Benefits:**

- Reproducible builds
- Controlled updates
- Security patch management

---

## Logging & Monitoring

### Security Event Logging

**What to Log:**

- Authentication attempts (success/failure)
- Authorization failures
- Input validation failures
- File operations (create, read, update, delete)
- Git operations
- Rate limit violations
- Configuration changes

**What NOT to Log:**

- Passwords or credentials
- API keys or tokens
- Personal identifiable information (PII)
- Full request/response bodies (may contain sensitive data)

### Log Format

```python
logger.info(
    "File operation",
    extra={
        "operation": "write",
        "file_path": sanitized_path,
        "user_id": user_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "result": "success"
    }
)
```

### Monitoring Alerts

**Alert On:**

- Multiple authentication failures
- Unusual file access patterns
- Rate limit violations
- Git operation failures
- Path validation failures

---

## Security Testing Guide

### Overview

Security testing is essential for maintaining the security posture of Cortex. This guide provides practical guidance for writing and running security tests.

### Test Categories

**1. Input Validation Tests**

Test all input validation functions with malicious inputs:

```python
import pytest
from cortex.core.security import InputValidator

class TestInputValidation:
    """Test input validation security."""

    def test_path_traversal_attack(self):
        """Test protection against path traversal."""
        with pytest.raises(ValueError, match="path traversal"):
            InputValidator.validate_file_name("../etc/passwd")

    def test_windows_reserved_names(self):
        """Test Windows reserved name blocking."""
        with pytest.raises(ValueError, match="reserved"):
            InputValidator.validate_file_name("CON")

    def test_invalid_characters(self):
        """Test invalid character rejection."""
        with pytest.raises(ValueError, match="invalid characters"):
            InputValidator.validate_file_name("test<file>.md")
```

**2. Sandbox Escape Tests**

Test that file operations are properly sandboxed:

```python
import tempfile
from pathlib import Path
from cortex.core.file_system import FileSystemManager

@pytest.mark.asyncio
async def test_sandbox_escape_attempt():
    """Test that operations outside project root are blocked."""
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir) / "project"
        project_root.mkdir()

        fs_manager = FileSystemManager(project_root)
        outside_path = Path(tmpdir) / "outside.txt"

        # Should not allow access outside project root
        assert not fs_manager.validate_path(outside_path)

        with pytest.raises(PermissionError):
            await fs_manager.read_file(outside_path)
```

**3. Rate Limiting Tests**

Test that rate limiting prevents abuse:

```python
import asyncio
from cortex.core.security import RateLimiter

@pytest.mark.asyncio
async def test_rate_limiting_enforcement():
    """Test that rate limiter blocks excessive operations."""
    limiter = RateLimiter(max_ops=5, window_seconds=1.0)

    # Fill up the limit
    for _ in range(5):
        await limiter.acquire()

    # Next operation should wait
    start = asyncio.get_event_loop().time()
    await limiter.acquire()
    elapsed = asyncio.get_event_loop().time() - start

    assert elapsed >= 0.9  # Should have waited ~1 second
```

**4. Git URL Validation Tests**

Test protection against malicious git URLs:

```python
from cortex.core.security import InputValidator

def test_git_url_localhost_blocked():
    """Test that localhost URLs are blocked."""
    with pytest.raises(ValueError, match="localhost"):
        InputValidator.validate_git_url("https://localhost/repo.git")

def test_git_url_private_ip_blocked():
    """Test that private IP addresses are blocked."""
    with pytest.raises(ValueError, match="private IP"):
        InputValidator.validate_git_url("https://192.168.1.1/repo.git")

def test_git_url_file_protocol_blocked():
    """Test that file:// protocol is blocked."""
    with pytest.raises(ValueError, match="Invalid git URL protocol"):
        InputValidator.validate_git_url("file:///path/to/repo")
```

### Running Security Tests

**Run all security tests:**

```bash
# Run security test files
pytest tests/unit/test_security.py -v

# Run with coverage
pytest tests/unit/test_security.py --cov=src/cortex/core/security --cov-report=term-missing

# Run security-related tests across all modules
pytest -k "security or validation" -v
```

**Run specific test categories:**

```bash
# Input validation tests only
pytest tests/unit/test_security.py::TestInputValidator -v

# Rate limiting tests only
pytest tests/unit/test_security.py::TestRateLimiter -v

# Git URL validation tests
pytest tests/unit/test_security_enhancements.py::TestGitURLValidation -v
```

### Security Test Checklist

When adding new features, ensure you test:

- [ ] All user inputs are validated
- [ ] File paths cannot escape project root
- [ ] No shell injection vulnerabilities
- [ ] Rate limiting is enforced
- [ ] Error messages don't leak sensitive data
- [ ] Resource limits are respected
- [ ] Git operations validate URLs
- [ ] No hardcoded credentials

### Writing New Security Tests

**Template for security tests:**

```python
"""Security tests for [feature name]."""

import pytest
from cortex.core.security import InputValidator

class Test[Feature]Security:
    """Test security aspects of [feature]."""

    def test_[feature]_input_validation(self):
        """Test that [feature] validates all inputs."""
        # Arrange: Prepare malicious input
        malicious_input = "../../etc/passwd"

        # Act & Assert: Should raise ValueError
        with pytest.raises(ValueError, match="path traversal"):
            # Call function with malicious input
            validate_function(malicious_input)

    @pytest.mark.asyncio
    async def test_[feature]_rate_limiting(self):
        """Test that [feature] enforces rate limits."""
        # Arrange: Create rate limiter
        limiter = RateLimiter(max_ops=5, window_seconds=1.0)

        # Act: Exceed rate limit
        for _ in range(5):
            await limiter.acquire()

        # Assert: Next operation should wait
        start = asyncio.get_event_loop().time()
        await limiter.acquire()
        elapsed = asyncio.get_event_loop().time() - start
        assert elapsed >= 0.9
```

### Security Testing Tools

**Static Analysis:**

```bash
# Bandit - Python security linter
bandit -r src/cortex/

# Safety - Dependency vulnerability scanner
safety check

# pip-audit - Another dependency scanner
pip-audit
```

**Dynamic Analysis:**

```bash
# pytest with security markers
pytest -m security -v

# Coverage with security focus
pytest --cov=src/cortex/core/security --cov-report=html

# Performance testing for DoS resistance
pytest tests/unit/test_security.py::TestRateLimiter -v --durations=10
```

### Continuous Security Testing

**Pre-commit hooks:**

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/PyCQA/bandit
    rev: 1.7.4
    hooks:
      - id: bandit
        args: ['-r', 'src/']
```

**CI/CD integration:**

```yaml
# .github/workflows/security.yml
name: Security Tests
on: [push, pull_request]

jobs:
  security:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Run security tests
        run: |
          pytest tests/unit/test_security*.py -v
          bandit -r src/
          safety check
```

---

## Incident Response

### Security Incident Handling

**Steps:**

1. **Detection** - Identify security incident
2. **Containment** - Limit damage and prevent spread
3. **Investigation** - Determine scope and impact
4. **Remediation** - Fix vulnerabilities
5. **Recovery** - Restore normal operations
6. **Lessons Learned** - Document and improve

### Incident Categories

**High Severity:**

- Unauthorized access to sensitive data
- Data breach or leak
- System compromise
- Malware infection

**Medium Severity:**

- Authentication bypass attempts
- Privilege escalation attempts
- Denial of service attacks
- Configuration errors

**Low Severity:**

- Failed authentication attempts
- Input validation failures
- Rate limit violations

### Reporting

**Internal Reporting:**

- Notify security team immediately
- Document incident details
- Preserve evidence
- Follow incident response plan

**External Reporting:**

- Notify affected users (if applicable)
- Report to authorities (if required)
- Coordinate with legal team
- Issue security advisories

---

## Security Checklist

### Development Phase

- [ ] Input validation implemented for all external inputs
- [ ] Path validation for all file operations
- [ ] Git URL validation for repository operations
- [ ] Rate limiting configured
- [ ] Sensitive data sanitized in logs
- [ ] Error messages don't leak sensitive information
- [ ] Dependencies scanned for vulnerabilities
- [ ] Security tests written and passing

### Code Review Phase

- [ ] Input validation reviewed
- [ ] Authentication/authorization checked
- [ ] Sensitive data handling reviewed
- [ ] Error handling verified
- [ ] Logging reviewed for sensitive data
- [ ] Dependencies reviewed
- [ ] Security tests reviewed

### Deployment Phase

- [ ] Environment variables configured securely
- [ ] SSL/TLS certificates valid
- [ ] Rate limiting enabled
- [ ] Monitoring and alerting configured
- [ ] Backup and recovery tested
- [ ] Incident response plan reviewed
- [ ] Security documentation updated

### Maintenance Phase

- [ ] Dependencies updated regularly
- [ ] Security patches applied promptly
- [ ] Logs reviewed for security events
- [ ] Access controls reviewed
- [ ] Security tests maintained
- [ ] Security documentation kept current

---

## Additional Resources

### Internal Documentation

- [Architecture Documentation](../architecture.md)
- [API Documentation](../api/tools.md)
- [Development Guide](../development/contributing.md)

### External Resources

- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [CWE/SANS Top 25](https://cwe.mitre.org/top25/)
- [Python Security Best Practices](https://python.readthedocs.io/en/stable/library/security_warnings.html)

---

## Contact

For security concerns or to report vulnerabilities:

- **Security Team:** <security@example.com>
- **Issue Tracker:** [GitHub Issues](https://github.com/username/cortex/issues)
- **Security Policy:** [SECURITY.md](../../SECURITY.md)

---

**Remember:** Security is everyone's responsibility. When in doubt, ask the security team.
