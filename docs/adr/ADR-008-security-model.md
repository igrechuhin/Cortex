# ADR-008: Security Model

## Status

Accepted

## Context

Cortex handles sensitive user data including:

1. **Memory Bank Files**: Project documentation, architecture notes, progress tracking
2. **Source Code References**: Code patterns, file structures
3. **Personal Information**: Developer notes, team communication
4. **Project Secrets**: Potentially API keys, credentials in examples
5. **File System Access**: Read/write operations across project directories

As an MCP server running locally with Claude Desktop, we must ensure:

- **User data protection**: No unauthorized access or data leakage
- **File system safety**: Prevent path traversal and unauthorized access
- **Input validation**: Sanitize all user inputs
- **Secure operations**: Atomic writes, proper locking, conflict detection
- **Privacy**: No telemetry, no data sent to cloud without consent

### Threat Model

**Assets to Protect**:
1. Memory bank files (`.cursor/memory-bank/*.md`)
2. Project source code
3. File system integrity
4. User privacy
5. System resources

**Threat Actors**:
1. **Malicious User Input**: Path traversal, command injection
2. **Compromised Dependencies**: Vulnerable third-party libraries
3. **Local Privilege Escalation**: Unauthorized file access
4. **Data Exfiltration**: Memory bank data leaked
5. **Denial of Service**: Resource exhaustion

**Attack Vectors**:
1. **Path Traversal**: `../../etc/passwd` in file paths
2. **Command Injection**: Shell commands in file names
3. **Symlink Attacks**: Symlinks to sensitive files
4. **Race Conditions**: TOCTOU (Time-of-Check-Time-of-Use)
5. **Resource Exhaustion**: Large files, deep recursion, memory bombs
6. **Transclusion Exploits**: Infinite loops, external file inclusion

### Security Requirements

**Confidentiality**:
- Memory bank files only accessible to authorized user
- No data sent to external services without explicit consent
- Sensitive data never logged
- Secure file permissions

**Integrity**:
- Files protected from unauthorized modification
- Atomic operations prevent corruption
- Hash verification detects tampering
- Conflict detection prevents data loss

**Availability**:
- Resilient to malformed inputs
- Resource limits prevent DoS
- Graceful degradation on errors
- Fast recovery from failures

**Compliance**:
- GDPR compliance (user data privacy)
- No telemetry without consent
- Right to delete data
- Data portability

### Existing Security Patterns

**Python Security Best Practices**:
- Use `pathlib.Path` for path operations (safer than string manipulation)
- Validate file paths against base directory
- Use `aiofiles` for safe async I/O
- Avoid `eval()`, `exec()`, `__import__()` with user input
- Use parameterized queries (if database used)

**File System Security**:
- Check file existence before operations
- Use exclusive locks for writes
- Atomic write operations (write to temp, then rename)
- Proper error handling for file operations

**Input Validation**:
- Whitelist allowed characters
- Validate file extensions
- Check file sizes
- Limit recursion depth

## Decision

We will implement a **defense-in-depth security model** with multiple layers:

1. **Path Traversal Protection**: Validate all file paths against allowed directories
2. **Input Validation**: Strict validation of all user inputs
3. **Secure File Operations**: Atomic writes, exclusive locks, conflict detection
4. **Resource Limits**: Bounds on file size, recursion depth, memory usage
5. **Privacy-First**: No telemetry, local-only by default
6. **Dependency Security**: Minimal dependencies, regular security audits

### Security Architecture

**Layer 1: Input Validation**

All user inputs validated before processing:

```python
from pathlib import Path
import re

class SecurityValidator:
    """Validate inputs for security."""

    # Allowed filename pattern (alphanumeric, dash, underscore, dot)
    FILENAME_PATTERN = re.compile(r'^[a-zA-Z0-9._-]+$')

    # Maximum file size (10 MB)
    MAX_FILE_SIZE = 10 * 1024 * 1024

    # Maximum path depth
    MAX_PATH_DEPTH = 20

    # Maximum transclusion depth
    MAX_TRANSCLUSION_DEPTH = 10

    @staticmethod
    def validate_filename(filename: str) -> bool:
        """Validate filename is safe."""
        # Check against pattern
        if not SecurityValidator.FILENAME_PATTERN.match(filename):
            raise SecurityError(f"Invalid filename: {filename}")

        # Reject special names
        if filename in [".", "..", ""]:
            raise SecurityError(f"Invalid filename: {filename}")

        # Reject hidden files (starting with .)
        if filename.startswith(".") and filename not in [".gitignore"]:
            raise SecurityError(f"Hidden files not allowed: {filename}")

        return True

    @staticmethod
    def validate_file_size(size: int) -> bool:
        """Validate file size is within limits."""
        if size > SecurityValidator.MAX_FILE_SIZE:
            raise SecurityError(
                f"File too large: {size} bytes (max: {SecurityValidator.MAX_FILE_SIZE})"
            )
        return True

    @staticmethod
    def validate_path_depth(path: Path) -> bool:
        """Validate path depth is within limits."""
        depth = len(path.parts)
        if depth > SecurityValidator.MAX_PATH_DEPTH:
            raise SecurityError(
                f"Path too deep: {depth} levels (max: {SecurityValidator.MAX_PATH_DEPTH})"
            )
        return True
```

**Layer 2: Path Traversal Protection**

All file paths validated against base directory:

```python
class PathValidator:
    """Validate file paths for security."""

    def __init__(self, base_dir: Path):
        """Initialize with base directory."""
        self.base_dir = base_dir.resolve()

    def validate_path(self, path: str | Path) -> Path:
        """Validate path is within base directory.

        Args:
            path: Path to validate (relative or absolute)

        Returns:
            Resolved absolute path within base directory

        Raises:
            SecurityError: If path is outside base directory
        """
        # Convert to Path object
        if isinstance(path, str):
            path = Path(path)

        # Resolve to absolute path (follows symlinks, resolves ..)
        resolved = (self.base_dir / path).resolve()

        # Check if resolved path is within base directory
        try:
            resolved.relative_to(self.base_dir)
        except ValueError:
            raise SecurityError(
                f"Path traversal detected: {path} resolves to {resolved} "
                f"which is outside base directory {self.base_dir}"
            )

        return resolved

    def is_safe_path(self, path: str | Path) -> bool:
        """Check if path is safe (no exceptions)."""
        try:
            self.validate_path(path)
            return True
        except SecurityError:
            return False
```

**Layer 3: Secure File Operations**

Atomic operations with conflict detection:

```python
import hashlib
import fcntl  # Unix file locking

class SecureFileSystem:
    """Secure file system operations."""

    def __init__(self, base_dir: Path):
        self.base_dir = base_dir
        self.path_validator = PathValidator(base_dir)
        self._locks: dict[str, asyncio.Lock] = {}

    async def read_file_secure(self, path: str) -> str:
        """Read file with security checks."""
        # Validate path
        resolved = self.path_validator.validate_path(path)

        # Check file exists
        if not resolved.exists():
            raise FileNotFoundError(f"File not found: {path}")

        # Check file size
        size = resolved.stat().st_size
        SecurityValidator.validate_file_size(size)

        # Read file
        async with aiofiles.open(resolved, "r", encoding="utf-8") as f:
            content = await f.read()

        return content

    async def write_file_atomic(
        self,
        path: str,
        content: str,
        expected_hash: str | None = None
    ) -> None:
        """Write file atomically with conflict detection.

        Args:
            path: File path to write
            content: Content to write
            expected_hash: Expected hash of existing file (conflict detection)

        Raises:
            SecurityError: Path validation failed
            ConflictError: File modified since read (hash mismatch)
        """
        # Validate path
        resolved = self.path_validator.validate_path(path)

        # Get lock for this file
        lock = self._get_lock(str(resolved))

        async with lock:
            # Conflict detection
            if expected_hash and resolved.exists():
                current_hash = await self._calculate_hash(resolved)
                if current_hash != expected_hash:
                    raise ConflictError(
                        f"File modified since read: {path}. "
                        f"Expected hash: {expected_hash}, "
                        f"Current hash: {current_hash}"
                    )

            # Write to temporary file
            temp_path = resolved.with_suffix(resolved.suffix + ".tmp")

            async with aiofiles.open(temp_path, "w", encoding="utf-8") as f:
                await f.write(content)

            # Atomic rename (overwrites existing file)
            temp_path.rename(resolved)

    async def _calculate_hash(self, path: Path) -> str:
        """Calculate SHA-256 hash of file."""
        hasher = hashlib.sha256()

        async with aiofiles.open(path, "rb") as f:
            while chunk := await f.read(8192):
                hasher.update(chunk)

        return hasher.hexdigest()

    def _get_lock(self, key: str) -> asyncio.Lock:
        """Get or create lock for key."""
        if key not in self._locks:
            self._locks[key] = asyncio.Lock()
        return self._locks[key]
```

**Layer 4: Transclusion Security**

Prevent infinite loops and unauthorized file access:

```python
class SecureTransclusionEngine:
    """Secure transclusion with safety checks."""

    def __init__(
        self,
        base_dir: Path,
        max_depth: int = 10,
        max_file_size: int = 10 * 1024 * 1024
    ):
        self.base_dir = base_dir
        self.max_depth = max_depth
        self.max_file_size = max_file_size
        self.path_validator = PathValidator(base_dir)

    async def resolve_transclusion(
        self,
        file_path: str,
        visited: set[str] | None = None,
        depth: int = 0
    ) -> str:
        """Resolve transclusions with security checks.

        Args:
            file_path: File to resolve
            visited: Set of visited files (circular dependency detection)
            depth: Current recursion depth

        Returns:
            Resolved content

        Raises:
            SecurityError: Path validation failed
            CircularDependencyError: Circular transclusion detected
            RecursionError: Max depth exceeded
        """
        # Check depth limit
        if depth > self.max_depth:
            raise RecursionError(
                f"Max transclusion depth exceeded: {depth} > {self.max_depth}"
            )

        # Initialize visited set
        if visited is None:
            visited = set()

        # Validate path
        resolved = self.path_validator.validate_path(file_path)
        resolved_str = str(resolved)

        # Check for circular dependency
        if resolved_str in visited:
            raise CircularDependencyError(
                f"Circular transclusion detected: {visited} -> {resolved_str}"
            )

        # Add to visited set
        visited.add(resolved_str)

        # Read file
        async with aiofiles.open(resolved, "r", encoding="utf-8") as f:
            content = await f.read()

        # Check file size
        if len(content) > self.max_file_size:
            raise SecurityError(
                f"File too large for transclusion: {len(content)} bytes"
            )

        # Parse transclusion links
        links = self._parse_transclusion_links(content)

        # Resolve each transclusion
        for link in links:
            # Validate link path
            try:
                link_resolved = self.path_validator.validate_path(link.target)
            except SecurityError as e:
                # Replace with error message
                content = content.replace(
                    f"{{{{include:{link.raw}}}}}",
                    f"[ERROR: {e}]"
                )
                continue

            # Recursively resolve
            try:
                included = await self.resolve_transclusion(
                    str(link_resolved),
                    visited.copy(),
                    depth + 1
                )

                # Replace transclusion with content
                content = content.replace(
                    f"{{{{include:{link.raw}}}}}",
                    included
                )
            except (CircularDependencyError, RecursionError) as e:
                # Replace with error message
                content = content.replace(
                    f"{{{{include:{link.raw}}}}}",
                    f"[ERROR: {e}]"
                )

        return content
```

**Layer 5: Resource Limits**

Prevent resource exhaustion:

```python
class ResourceLimiter:
    """Enforce resource limits."""

    def __init__(
        self,
        max_concurrent_operations: int = 100,
        max_memory_mb: int = 500,
        max_file_size_mb: int = 10
    ):
        self.max_concurrent_operations = max_concurrent_operations
        self.max_memory_mb = max_memory_mb
        self.max_file_size_mb = max_file_size_mb
        self._semaphore = asyncio.Semaphore(max_concurrent_operations)

    async def limit_concurrency(self, coro):
        """Limit concurrent operations."""
        async with self._semaphore:
            return await coro

    def check_memory_usage(self) -> None:
        """Check memory usage and raise if exceeded."""
        import psutil
        process = psutil.Process()
        memory_mb = process.memory_info().rss / 1024 / 1024

        if memory_mb > self.max_memory_mb:
            raise ResourceError(
                f"Memory limit exceeded: {memory_mb:.1f} MB > {self.max_memory_mb} MB"
            )

    async def read_file_with_limit(self, path: Path) -> str:
        """Read file with size limit."""
        size = path.stat().st_size
        size_mb = size / 1024 / 1024

        if size_mb > self.max_file_size_mb:
            raise ResourceError(
                f"File too large: {size_mb:.1f} MB > {self.max_file_size_mb} MB"
            )

        async with aiofiles.open(path, "r", encoding="utf-8") as f:
            return await f.read()
```

**Layer 6: Privacy Protection**

No telemetry, local-only by default:

```python
class PrivacyManager:
    """Manage privacy settings."""

    def __init__(self):
        self.telemetry_enabled = False  # Default: disabled
        self.cloud_sync_enabled = False  # Default: disabled

    def is_telemetry_allowed(self) -> bool:
        """Check if telemetry is allowed."""
        return self.telemetry_enabled

    def is_cloud_sync_allowed(self) -> bool:
        """Check if cloud sync is allowed."""
        return self.cloud_sync_enabled

    def sanitize_for_logging(self, message: str) -> str:
        """Sanitize message for logging (remove sensitive data)."""
        # Remove potential file paths
        message = re.sub(r'/[^\s]+', '[PATH]', message)

        # Remove potential API keys (long alphanumeric strings)
        message = re.sub(r'[a-zA-Z0-9]{32,}', '[REDACTED]', message)

        # Remove potential emails
        message = re.sub(r'[\w\.-]+@[\w\.-]+', '[EMAIL]', message)

        return message
```

### Security Testing

**Unit Tests**:

```python
import pytest

async def test_path_traversal_blocked():
    """Test path traversal is blocked."""
    validator = PathValidator(Path("/home/user/project"))

    with pytest.raises(SecurityError):
        validator.validate_path("../../etc/passwd")

    with pytest.raises(SecurityError):
        validator.validate_path("/etc/passwd")

async def test_circular_dependency_detected():
    """Test circular dependency detection."""
    engine = SecureTransclusionEngine(Path("/test"))

    # Create circular reference: A includes B, B includes A
    with pytest.raises(CircularDependencyError):
        await engine.resolve_transclusion("a.md", visited={"b.md"})

async def test_file_size_limit():
    """Test file size limit enforced."""
    limiter = ResourceLimiter(max_file_size_mb=1)

    # Create large file (2 MB)
    large_file = Path("/tmp/large.txt")
    large_file.write_text("x" * (2 * 1024 * 1024))

    with pytest.raises(ResourceError):
        await limiter.read_file_with_limit(large_file)
```

**Security Audit Checklist**:

- [ ] All file paths validated against base directory
- [ ] No user input passed to shell commands
- [ ] All file operations use atomic writes
- [ ] File size limits enforced
- [ ] Recursion depth limits enforced
- [ ] No secrets in logs
- [ ] No telemetry without consent
- [ ] Dependencies regularly updated
- [ ] Security tests pass

### Dependency Security

**Minimal Dependencies**:
- `mcp` - MCP SDK (trusted)
- `aiofiles` - Async file I/O (widely used, simple)
- `pydantic` - Data validation (trusted)

**Security Practices**:
- Pin dependency versions
- Regular security audits (`pip-audit`)
- Monitor for CVEs
- Update promptly when vulnerabilities found

**Dependency Pinning** (`pyproject.toml`):

```toml
[project]
dependencies = [
    "mcp>=0.9.0,<0.10.0",
    "aiofiles>=23.2.0,<24.0.0",
    "pydantic>=2.5.0,<3.0.0"
]
```

## Consequences

### Positive

**1. Defense in Depth**:
- Multiple security layers
- Failure in one layer doesn't compromise security
- Redundant protections
- Comprehensive coverage

**2. Path Traversal Protection**:
- All file paths validated
- Symlink resolution secure
- Base directory enforcement
- No unauthorized file access

**3. Data Integrity**:
- Atomic operations prevent corruption
- Conflict detection prevents data loss
- Hash verification detects tampering
- File locking prevents race conditions

**4. Privacy-First**:
- No telemetry by default
- All data local
- User controls data
- GDPR compliant

**5. Resource Protection**:
- Prevents DoS attacks
- Memory limits enforced
- File size limits enforced
- Recursion depth limits enforced

**6. Testable Security**:
- Security tests for all threat vectors
- Clear security requirements
- Automated security checks
- Audit trail

### Negative

**1. Performance Overhead**:
- Path validation adds latency (~1ms per operation)
- Hash calculation for conflict detection (~10ms for 1MB file)
- File locking adds contention
- Resource checks add overhead

**2. Complexity**:
- Multiple security layers to maintain
- More code to test
- Error handling more complex
- Debugging harder

**3. False Positives**:
- Legitimate operations may be blocked
- Path validation may be too strict
- File size limits may be too low
- Need configuration options

**4. User Experience**:
- Security errors can be confusing
- Users may not understand why operations blocked
- Need clear error messages
- Need documentation

**5. Maintenance Burden**:
- Security updates required
- Dependency monitoring needed
- Regular audits required
- Stay current with threats

**6. Limited Flexibility**:
- Base directory restriction may be limiting
- File size limits may be insufficient for large projects
- Recursion depth limits may be too low
- Need escape hatches with caution

### Neutral

**1. Threat Model Assumptions**:
- Assumes local attacker (not remote)
- Assumes MCP protocol is secure
- Assumes Claude Desktop is trusted
- Context-dependent

**2. Security vs Usability**:
- Trade-off: strict security vs user freedom
- Balance required
- Configuration options help
- User education important

**3. Zero Trust**:
- All inputs validated (including from Claude)
- Paranoid approach
- May seem excessive
- Better safe than sorry

## Alternatives Considered

### Alternative 1: Minimal Security (Trust Everything)

**Approach**: Trust all inputs, no validation.

**Pros**:
- Simple implementation
- No overhead
- Maximum flexibility
- Fast

**Cons**:
- Vulnerable to all attacks
- No data protection
- No integrity guarantees
- Unacceptable risk

**Rejection Reason**: Violates fundamental security requirements. Unacceptable risk.

### Alternative 2: Sandboxing (OS-Level)

**Approach**: Run in sandboxed environment (Docker, firejail, etc.).

**Pros**:
- Strong isolation
- OS-level protection
- Proven technology
- Defense against unknown threats

**Cons**:
- Requires Docker/container runtime
- Complex setup
- Performance overhead
- Platform-specific

**Rejection Reason**: Too complex for local tool. Adds deployment complexity.

### Alternative 3: Capability-Based Security

**Approach**: User grants explicit capabilities for each operation.

**Pros**:
- Fine-grained control
- Explicit authorization
- Clear permissions
- Good user understanding

**Cons**:
- Poor user experience (too many prompts)
- Friction in workflow
- Users may approve everything
- Not suitable for MCP

**Rejection Reason**: Too much friction. MCP model assumes trust within workspace.

### Alternative 4: Cryptographic Verification

**Approach**: Sign all files, verify signatures on read.

**Pros**:
- Strong integrity guarantees
- Detect any tampering
- Non-repudiation
- Audit trail

**Cons**:
- Complex key management
- Performance overhead
- Overkill for local tool
- User friction (key setup)

**Rejection Reason**: Overkill for local tool. Hash verification sufficient.

### Alternative 5: Read-Only Mode

**Approach**: Only allow reading, no writes.

**Pros**:
- No data integrity concerns
- Very safe
- Simple implementation
- No conflicts possible

**Cons**:
- Can't create or modify memory bank
- Defeats purpose of tool
- Users want write access
- Not useful

**Rejection Reason**: Memory bank requires write access. Read-only defeats purpose.

### Alternative 6: External Security Service

**Approach**: Call external service for security decisions.

**Pros**:
- Centralized security logic
- Expert security decisions
- Regular updates
- Shared threat intelligence

**Cons**:
- Network dependency
- Privacy concerns
- Latency overhead
- Single point of failure

**Rejection Reason**: Violates local-first principle. Privacy concerns.

## Implementation Notes

### Security Checklist

Before any release:

1. **Code Review**: Security-focused code review
2. **Dependency Audit**: Run `pip-audit` to check for vulnerabilities
3. **Security Tests**: All security tests pass
4. **Penetration Testing**: Test common attack vectors
5. **Documentation**: Security documentation up to date
6. **Logging**: Verify no sensitive data in logs
7. **Permissions**: Check file permissions on created files

### Incident Response

If security vulnerability discovered:

1. **Assess Severity**: Use CVSS scoring
2. **Develop Fix**: Prioritize based on severity
3. **Test Fix**: Verify fix doesn't break functionality
4. **Release Patch**: Release security update
5. **Notify Users**: Security advisory if needed
6. **Post-Mortem**: Learn from incident

### Security Contact

Report security issues to: security@cortex.dev (future)

### Regular Security Tasks

- **Weekly**: Monitor dependency vulnerabilities
- **Monthly**: Review security logs
- **Quarterly**: Security code review
- **Annually**: Penetration testing

## References

- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [CWE Top 25](https://cwe.mitre.org/top25/archive/2023/2023_top25_list.html)
- [Python Security Best Practices](https://python.readthedocs.io/en/stable/library/security_warnings.html)
- [Path Traversal Prevention](https://owasp.org/www-community/attacks/Path_Traversal)
- [GDPR Compliance](https://gdpr.eu/)

## Related ADRs

- ADR-001: Hybrid Storage - Secure file storage
- ADR-002: DRY Linking - Transclusion security
- ADR-006: Async-First Design - Secure async operations
- ADR-007: Learning Engine - Privacy-preserving learning

## Revision History

- 2024-01-10: Initial version (accepted)
