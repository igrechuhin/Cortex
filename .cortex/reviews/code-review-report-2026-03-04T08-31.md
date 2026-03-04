# Code Review Report — 2026-03-04T08-31

## Scope

Full codebase review of the Cortex project — 537 Python source files, 294 test files, 32 main modules in `src/cortex/`.

**Primary theme**: Comprehensive codebase health audit covering static analysis, bug detection, consistency, rules compliance, completeness, test coverage, security, and performance.

---

## Code Quality Assessment

- **Overall Score: 7.4 / 10**
- **Detailed Reasoning**: The codebase is well-structured with strong type safety (pyright clean, ruff clean), excellent test coverage (92.43%, 4891 tests passing), and solid architectural patterns (dependency injection, protocol-based abstractions, layered architecture). However, several significant issues exist: security vulnerabilities (`exec()` with file input), race conditions in file locking (TOCTOU), performance anti-patterns (O(n) cache eviction, blocking event loop with `time.sleep`), and rules compliance gaps (TypedDict usage, TYPE_CHECKING imports, type-checker suppressions). The sync-in-async pattern across 25+ locations is a systemic concern.
- **Strengths**:
  - Zero pyright errors and ruff violations — clean static analysis
  - 92.43% test coverage with 4891 passing tests (3 skipped, 0 failures)
  - Consistent Pydantic v2 model usage throughout production code
  - Strong architectural layering (MCP Server → Tools → Managers → Business Logic → Core)
  - Dependency injection pattern well-established
  - Comprehensive test edge-case coverage
- **Weaknesses**:
  - `exec()` with file-derived input (security vulnerability)
  - TOCTOU race conditions in file-based locking
  - Sync file I/O in async paths (25+ locations)
  - 8 TypedDict classes violating Python coding standards
  - 17 type-checker suppressions in codebase
  - Inconsistent response format patterns across tool modules

---

## Detailed Metrics Scoring

| Metric | Score | Reasoning |
|--------|-------|-----------|
| **Architecture** | 8/10 | Strong layered architecture, dependency injection, protocol-based abstractions. Deducted for some model files with 20-38 public classes violating one-type-per-file rule, and `StructureManager` instantiated directly instead of via container. |
| **Test Coverage** | 8/10 | 92.43% overall coverage (4891 tests, 0 failures). AAA pattern followed. Deducted for some modules below 85% (query_handlers.py 82.82%, production_monitoring_helpers.py 83.58%) and result_links_models.py at 0%. |
| **Documentation** | 7/10 | Module docstrings present, memory bank maintained. Deducted for `_migrate_doc_mcp_style` stub without implementation, and some silent error swallowing blocks without documentation. |
| **Code Style** | 8/10 | Ruff passes clean, consistent naming conventions, proper import organization. Deducted for inconsistent response format patterns (`"status": "success"` vs `"success": true`). |
| **Error Handling** | 7/10 | Generally good error handling patterns. Deducted for 11 broad `except Exception: pass` blocks that silently swallow errors, and `is_connection_error` over-matching "resource" keyword. |
| **Performance** | 6/10 | Deducted significantly for: LRU Cache with O(n) list operations, `list.pop(0)` in BFS queues, `time.sleep()` blocking event loop, 25+ sync file I/O in async paths, sequential file reading without parallelism, un-cached regex compilations. |
| **Security** | 6/10 | Deducted for: `exec()` with file-derived input (HIGH), TOCTOU in file locking (HIGH), incomplete SSRF bypass protection, prompt file loading without path validation, missing subprocess timeouts. |
| **Maintainability** | 7/10 | Good module organization with helper extraction pattern. Deducted for 30 files exceeding 400 total lines (though many pass when excluding imports/comments), three competing error response patterns, and two patterns for accessing `get_managers`. |
| **Rules Compliance** | 7/10 | No `Any` type in production, Pydantic v2 throughout, no bare except, no singletons. Deducted for 8 TypedDict classes, 2 TYPE_CHECKING imports, ~17 type-checker suppressions, and inconsistent response format. |

**Overall Score: 7.1/10** (average of all metrics)

---

## Critical Issues (Must-Fix)

### Issue 1: `exec()` with File-Derived Input

- **Title**: Unsafe `exec()` usage with file-derived content
- **Severity**: Critical (Security)
- **Priority**: ASAP
- **Impact**: Arbitrary code execution if prompt files are tampered with. Even with trusted files, `exec()` is a known attack vector for supply-chain compromises.
- **Location**: [prompts.py](src/cortex/tools/synapse/prompts.py) — `exec()` call with content read from prompt files
- **Current State**: File content passed to `exec()` for prompt rendering
- **Expected State**: Use a safe template engine (e.g., Jinja2 with sandboxed environment) or simple string formatting
- **Root Cause**: Dynamic prompt execution implemented via `exec()` instead of template-based rendering
- **Dependencies**: None
- **Prerequisites**: None
- **Implementation Steps**:
  1. Replace `exec()` with safe template rendering (Jinja2 sandboxed or `string.Template`)
  2. Add path validation to restrict prompt file loading to known directories
  3. Add input sanitization for any user-provided template variables
  4. Add tests for path traversal prevention
- **Technical Design**: Replace dynamic code execution with declarative template rendering
- **Testing Strategy**: Test with malicious template content, path traversal attempts, and normal prompt rendering
- **Success Criteria**: Zero `exec()` calls in production code; prompt rendering uses safe templating
- **Estimated Effort**: Medium (4-8h)
- **Risks**: Medium — must ensure all existing prompt functionality still works with the new rendering approach

### Issue 2: TOCTOU Race Condition in File-Based Locking

- **Title**: Time-of-check-to-time-of-use race in file locking
- **Severity**: High (Bug)
- **Priority**: ASAP
- **Impact**: Concurrent processes can corrupt shared state (lock files, cache JSON) under multi-agent scenarios
- **Location**:
  - [file_system.py](src/cortex/core/file_system.py) — file lock acquisition
  - [cache_json_access.py](src/cortex/core/cache_json_access.py) — cache file read-write
- **Current State**: Check-then-act pattern with file existence check followed by lock acquisition, with a window between check and act
- **Expected State**: Atomic lock acquisition using `fcntl.flock()` or `os.open(O_CREAT | O_EXCL)` patterns
- **Root Cause**: File existence check and lock acquisition are not atomic
- **Dependencies**: None
- **Prerequisites**: None
- **Implementation Steps**:
  1. Replace check-then-act with atomic `O_CREAT | O_EXCL` or `fcntl.flock()`
  2. Add retry logic with exponential backoff for lock contention
  3. Add lock timeout to prevent deadlocks
  4. Add tests for concurrent lock acquisition
- **Technical Design**: Use POSIX advisory locking (fcntl) for atomic lock operations
- **Testing Strategy**: Concurrent lock acquisition tests, lock timeout tests, lock contention tests
- **Success Criteria**: Lock acquisition is atomic; no TOCTOU window exists
- **Estimated Effort**: Medium (4-8h)
- **Risks**: Medium — must handle cross-platform differences (macOS vs Linux lock semantics)

### Issue 3: `is_connection_error` Over-Matches on "resource"

- **Title**: Connection error detection over-matches due to "resource" keyword
- **Severity**: High (Bug)
- **Priority**: High
- **Impact**: Legitimate errors containing "resource" in the message are incorrectly classified as connection errors, triggering retry logic instead of proper error handling
- **Location**: [mcp_stability_config.py](src/cortex/core/mcp_stability_config.py) — `is_connection_error` function
- **Current State**: String matching on "resource" catches unrelated errors (e.g., "resource not found", "resource limit exceeded")
- **Expected State**: More specific matching (e.g., "resource temporarily unavailable" or exact error code matching)
- **Root Cause**: Overly broad string pattern matching without context
- **Dependencies**: None
- **Prerequisites**: Catalog actual connection error messages to build precise patterns
- **Implementation Steps**:
  1. Audit all actual connection error messages from MCP framework
  2. Replace broad "resource" match with specific patterns or error codes
  3. Add tests for false-positive scenarios
- **Technical Design**: Use error code-based matching where possible, fall back to specific message patterns
- **Testing Strategy**: Test with both true connection errors and false positives ("resource not found", etc.)
- **Success Criteria**: Zero false positives in connection error detection
- **Estimated Effort**: Low (2-4h)
- **Risks**: Low — must verify all real connection errors are still caught

### Issue 4: Non-Atomic Task Locking

- **Title**: Task locking mechanism is not atomic
- **Severity**: High (Bug)
- **Priority**: High
- **Impact**: Concurrent agents can acquire the same task lock, leading to duplicate work or data corruption
- **Location**: [task_locking.py](src/cortex/tools/session/task_locking.py)
- **Current State**: Lock acquisition involves multiple steps that are not atomic
- **Expected State**: Atomic compare-and-swap lock acquisition
- **Root Cause**: Multi-step lock protocol without atomicity guarantees
- **Dependencies**: Issue 2 (file-based locking TOCTOU)
- **Prerequisites**: None
- **Implementation Steps**:
  1. Implement atomic lock acquisition using file-system atomic operations
  2. Add lock owner identification (PID + timestamp)
  3. Add stale lock detection and cleanup
  4. Add concurrent lock acquisition tests
- **Technical Design**: Use `O_CREAT | O_EXCL` for atomic lock file creation with owner metadata
- **Testing Strategy**: Multi-process lock contention tests
- **Success Criteria**: Lock acquisition is atomic; concurrent agents cannot acquire the same lock
- **Estimated Effort**: Medium (4-8h)
- **Risks**: Medium — stale lock cleanup must handle edge cases (crashed processes)

### Issue 5: `time.sleep()` Blocking Event Loop

- **Title**: Synchronous sleep blocks async event loop
- **Severity**: High (Performance)
- **Priority**: High
- **Impact**: Event loop blocked during sleep, preventing all other async operations from executing. Causes degraded responsiveness in the MCP server.
- **Location**: [token_counter.py](src/cortex/core/token_counter.py)
- **Current State**: `time.sleep()` called in async context
- **Expected State**: `await asyncio.sleep()` for async contexts, or offload to thread executor
- **Root Cause**: Sync sleep used in async function
- **Dependencies**: None
- **Prerequisites**: None
- **Implementation Steps**:
  1. Replace `time.sleep()` with `await asyncio.sleep()` in async functions
  2. If called from sync context, ensure the caller chain is made async
  3. Add lint rule or pre-commit check to detect `time.sleep` in async functions
- **Technical Design**: Direct replacement with async equivalent
- **Testing Strategy**: Verify token counter works correctly with async sleep; verify no event loop blocking
- **Success Criteria**: Zero `time.sleep()` calls in async code paths
- **Estimated Effort**: Low (1-2h)
- **Risks**: Low — straightforward replacement

---

## Performance Issues

### Issue 6: LRU Cache O(n) Eviction

- **Title**: LRU Cache uses O(n) list operations for eviction
- **Severity**: High (Performance)
- **Priority**: High
- **Impact**: Cache operations degrade linearly with cache size. With large caches, eviction becomes a bottleneck.
- **Location**: [cache.py](src/cortex/core/cache.py)
- **Current State**: Uses list with `list.remove()` and `list.append()` for LRU tracking — O(n) for each access
- **Expected State**: Use `collections.OrderedDict` with `move_to_end()` — O(1) for all operations
- **Implementation Steps**:
  1. Replace list-based LRU tracking with `OrderedDict`
  2. Use `move_to_end()` for cache hits, `popitem(last=False)` for eviction
  3. Benchmark before/after with large cache sizes
- **Estimated Effort**: Low (2-4h)
- **Success Criteria**: All cache operations are O(1); benchmarks confirm improvement

### Issue 7: `list.pop(0)` in BFS Queues

- **Title**: BFS queues use `list.pop(0)` instead of `collections.deque`
- **Severity**: High (Performance)
- **Priority**: High
- **Impact**: O(n) dequeue operation makes BFS O(n^2) overall
- **Location**: [graph_algorithms.py](src/cortex/core/graph_algorithms.py)
- **Current State**: `queue = [start]; node = queue.pop(0)`
- **Expected State**: `queue = deque([start]); node = queue.popleft()`
- **Implementation Steps**:
  1. Import `deque` from collections
  2. Replace `list` with `deque` for BFS queues
  3. Replace `.pop(0)` with `.popleft()`
- **Estimated Effort**: Low (< 1h)
- **Success Criteria**: BFS queue operations are O(1)

### Issue 8: Sync File I/O in Async Paths (Systemic)

- **Title**: 25+ locations use synchronous file I/O in async code paths
- **Severity**: High (Performance)
- **Priority**: Medium (systemic — requires phased migration)
- **Impact**: Each sync I/O call blocks the event loop, reducing MCP server throughput and responsiveness
- **Location**: 25+ files across `src/cortex/` (core, optimization, tools, validation modules)
- **Current State**: `open()`, `os.path.exists()`, `os.listdir()`, `pathlib.Path.read_text()` in async functions
- **Expected State**: `aiofiles.open()`, `aiofiles.os.path.exists()`, `asyncio.to_thread()` wrappers
- **Implementation Steps**:
  1. Audit all async functions for sync file I/O calls
  2. Prioritize hot paths (context loading, cache access, session management)
  3. Replace with `aiofiles` equivalents or `asyncio.to_thread()` wrappers
  4. Add a lint rule to detect sync I/O in async functions
- **Estimated Effort**: High (16-24h across phased migration)
- **Success Criteria**: Zero sync file I/O in hot-path async functions

### Issue 9: Sequential File Reading in Context Loading

- **Title**: Context files loaded sequentially without parallelism
- **Severity**: High (Performance)
- **Priority**: Medium
- **Impact**: Context loading time scales linearly with number of files; could use `asyncio.gather()` for parallel I/O
- **Location**: Context loading module (optimization/context loading)
- **Current State**: Files read one at a time in a loop
- **Expected State**: `asyncio.gather()` for parallel file reads
- **Implementation Steps**:
  1. Identify sequential file reading loops in context loading
  2. Replace with `asyncio.gather()` for parallel reads
  3. Add concurrency limit to prevent file descriptor exhaustion
- **Estimated Effort**: Medium (4-8h)
- **Success Criteria**: Context loading time reduced; parallel I/O verified

---

## Security Issues

### Issue 10: Incomplete Private IP SSRF Bypass Protection

- **Title**: SSRF protection misses some private IP ranges
- **Severity**: Medium (Security)
- **Priority**: Medium
- **Impact**: Some private/reserved IP addresses not blocked, potentially allowing SSRF attacks through those ranges
- **Location**: [security.py](src/cortex/core/security.py) — IP validation function
- **Current State**: Blocks common private ranges (10.x, 172.16-31.x, 192.168.x) but misses some reserved ranges
- **Expected State**: Comprehensive blocklist including link-local (169.254.x), loopback (127.x), and other reserved ranges
- **Implementation Steps**:
  1. Add link-local (169.254.0.0/16), multicast (224.0.0.0/4), broadcast ranges
  2. Use `ipaddress.ip_address().is_private` for comprehensive checking
  3. Add tests for all RFC 5735 special-use ranges
- **Estimated Effort**: Low (2-4h)
- **Risks**: Low

### Issue 11: Prompt File Loading Without Path Validation

- **Title**: Prompt files loaded without path traversal protection
- **Severity**: Medium (Security)
- **Priority**: Medium
- **Impact**: Path traversal could allow loading files outside the prompts directory
- **Location**: [prompts.py](src/cortex/tools/synapse/prompts.py)
- **Current State**: File paths accepted without validation against a base directory
- **Expected State**: Path resolution with base directory enforcement (reject paths that escape prompts directory)
- **Implementation Steps**:
  1. Resolve the path using `Path.resolve()` and verify it starts with the expected prompts base directory
  2. Reject paths containing `..` after resolution
  3. Add test for path traversal attempts
- **Estimated Effort**: Low (1-2h)
- **Risks**: Low

### Issue 12: Missing Subprocess Timeouts

- **Title**: Some subprocess calls lack timeout parameter
- **Severity**: Low (Security)
- **Priority**: Low
- **Impact**: Subprocess can hang indefinitely, causing resource exhaustion
- **Location**: Various subprocess calls across the codebase
- **Implementation Steps**: Add timeout parameters to all subprocess calls
- **Estimated Effort**: Low (1-2h)

---

## Consistency Issues

### Issue 13: Response Format Split

- **Title**: `"status": "success"` vs `"success": true` split across tools
- **Severity**: High (Consistency)
- **Priority**: Medium
- **Impact**: Consumers must handle two different success/failure response formats, increasing complexity and error potential
- **Location**: Various tool modules in `src/cortex/tools/`
- **Current State**: Some tools return `{"status": "success", ...}`, others return `{"success": true, ...}`
- **Expected State**: Single consistent response format across all tools
- **Implementation Steps**:
  1. Define canonical response format (recommend `{"status": "success/error", ...}`)
  2. Create shared response builder utility
  3. Migrate all tools to use the shared builder
  4. Update tests
- **Estimated Effort**: High (16-24h — touches many tool modules)
- **Risks**: Medium — must coordinate with MCP client consumers

### Issue 14: Model Files with Multiple Public Classes

- **Title**: Model files contain 20-38 public classes violating one-type-per-file rule
- **Severity**: High (Rules Compliance)
- **Priority**: Medium
- **Impact**: Violates one-public-type-per-file rule, making files harder to navigate and maintain
- **Location**: Multiple model files in `src/cortex/tools/` subpackages
- **Implementation Steps**: Split each model file so each public class has its own file
- **Estimated Effort**: High (16-24h)

### Issue 15: Three Competing Error Response Patterns

- **Title**: Error responses constructed inconsistently
- **Severity**: Medium (Consistency)
- **Priority**: Medium
- **Location**: Various tool modules
- **Current State**: Three patterns: (1) `{"error": "message"}`, (2) `{"status": "error", "message": "..."}`, (3) `{"success": false, "error": "..."}`
- **Expected State**: Single error response pattern using shared builder
- **Implementation Steps**: Unify with response format standardization (Issue 13)

### Issue 16: Two Patterns for `get_managers` Access

- **Title**: Inconsistent manager access pattern
- **Severity**: Medium (Consistency)
- **Priority**: Low
- **Location**: Various tool modules
- **Current State**: Some modules call `get_managers()` directly, others receive managers via dependency injection
- **Expected State**: Consistent DI pattern throughout
- **Implementation Steps**: Refactor direct `get_managers()` calls to use injected managers

---

## Rules Violations

### Violation 1: TypedDict Usage (8 Classes)

- **Rule**: No TypedDict — use Pydantic BaseModel (Python coding standards)
- **Severity**: Medium
- **Impact**: TypedDict lacks runtime validation that Pydantic provides
- **Location**: 8 TypedDict classes across the codebase
- **Implementation Steps**: Replace each TypedDict with equivalent Pydantic BaseModel
- **Estimated Effort**: Medium (4-8h)

### Violation 2: TYPE_CHECKING Imports (2 Instances)

- **Rule**: No TYPE_CHECKING imports (Python coding standards)
- **Severity**: Medium
- **Location**: 2 files using `from __future__ import TYPE_CHECKING`
- **Implementation Steps**: Replace with direct imports; resolve any circular dependencies
- **Estimated Effort**: Low (2-4h)

### Violation 3: Type-Checker Suppressions (~17 Instances)

- **Rule**: No type-checker suppression comments (maintainability rules)
- **Severity**: Medium
- **Location**: ~17 instances of `# type: ignore`, `# pyright: ignore`, etc.
- **Implementation Steps**: Fix the underlying type errors; remove suppression comments
- **Estimated Effort**: Medium (4-8h)

### Violation 4: Sync File I/O in Async Code (~17 Files)

- **Rule**: Async-first I/O (Python coding standards)
- **Severity**: Medium
- **Location**: ~17 files with sync I/O in async paths (overlaps with Performance Issue 8)
- **Implementation Steps**: Migrate to aiofiles or asyncio.to_thread()

---

## Completeness Issues

### Issue 17: `_migrate_doc_mcp_style` Stub

- **Title**: Unimplemented migration function stub
- **Severity**: High (Completeness)
- **Priority**: Medium
- **Impact**: Migration path incomplete — if triggered, would silently fail or raise
- **Location**: [structure_migration.py](src/cortex/structure/structure_migration.py) — `_migrate_doc_mcp_style` function
- **Current State**: Stub/placeholder implementation
- **Expected State**: Full implementation or explicit removal with documentation
- **Implementation Steps**:
  1. Determine if migration is still needed
  2. If yes: implement the migration logic
  3. If no: remove the stub and document the decision
- **Estimated Effort**: Low-Medium (2-8h depending on scope)

### Issue 18: Silent Error Swallowing (11 Blocks)

- **Title**: Broad `except Exception: pass` blocks
- **Severity**: Medium (5 blocks) / Low (6 blocks)
- **Priority**: Medium
- **Impact**: Errors silently swallowed, making debugging difficult; failures may go unnoticed
- **Location**: 11 blocks across various modules
- **Current State**: `except Exception: pass` with no logging or re-raise
- **Expected State**: At minimum, log the exception; ideally, handle specific exceptions
- **Implementation Steps**:
  1. Audit each block to determine the expected exceptions
  2. Replace broad `except Exception` with specific exception types
  3. Add logging for all caught exceptions
  4. Remove `pass` — add proper handling or logged re-raise
- **Estimated Effort**: Medium (4-8h)

### Issue 19: `result_links_models.py` at 0% Coverage

- **Title**: Entirely uncovered module
- **Severity**: Medium (Completeness)
- **Priority**: Medium
- **Impact**: 87 statements with no test coverage — unknown correctness
- **Location**: [result_links_models.py](src/cortex/tools/validation/result_links_models.py) — lines 3-166
- **Current State**: 0% test coverage
- **Expected State**: 90%+ coverage per project standards
- **Implementation Steps**:
  1. Create test file for result_links_models.py
  2. Test all public classes and methods
  3. Cover edge cases per testing standards
- **Estimated Effort**: Medium (4-8h)

---

## Improvement Suggestions

### Improvement 1: Pre-Compile Regex Patterns

- **Category**: Performance
- **Priority**: Medium
- **Current State**: Regex patterns compiled on each call
- **Proposed State**: Pre-compile at module level using `re.compile()`
- **Benefits**: Avoids repeated compilation overhead
- **Estimated Effort**: Low (2-4h)

### Improvement 2: Replace O(n^2) Membership Checks

- **Category**: Performance
- **Priority**: Medium
- **Current State**: Some membership checks use lists (`if x in list`)
- **Proposed State**: Use sets for O(1) lookups (`if x in set`)
- **Estimated Effort**: Low (1-2h)

### Improvement 3: Add Token Counting Cache

- **Category**: Performance
- **Priority**: Medium
- **Current State**: Token counting performed without caching
- **Proposed State**: LRU cache for repeated token count operations on same content
- **Benefits**: Significant speedup for repeated context loading operations
- **Estimated Effort**: Low (2-4h)

### Improvement 4: Unify Response Format with Shared Builder

- **Category**: Consistency / Maintainability
- **Priority**: High
- **Current State**: Three different response patterns across tool modules
- **Proposed State**: Single `ResponseBuilder` utility used by all tools
- **Benefits**: Consistent API surface, easier testing, single point of change
- **Estimated Effort**: High (16-24h)

---

## Test Coverage Summary

| Metric | Value |
|--------|-------|
| **Total Tests** | 4891 passed, 3 skipped |
| **Overall Coverage** | 92.43% |
| **Execution Time** | 70.76s |
| **Warnings** | 28 |
| **Total Statements** | 30,290 |
| **Missed Statements** | 2,292 |

### Notable Coverage Gaps

| Module | Coverage | Missed Lines |
|--------|----------|--------------|
| `result_links_models.py` | 0.00% | 3-166 (87 stmts) |
| `query_handlers.py` | 82.82% | 203-260 (28 stmts) |
| `production_monitoring_helpers.py` | 83.58% | 42-50, 86-91 (11 stmts) |
| `roadmap_sync.py` (validation) | 86.36% | 93-99 (6 stmts) |
| `roadmap_sync.py` (core) | 90.69% | 276-480 (23 stmts) |

---

## Summary of Action Items

| Priority | Issue | Category | Effort |
|----------|-------|----------|--------|
| ASAP | Replace `exec()` with safe templating (Issue 1) | Security | Medium |
| ASAP | Fix TOCTOU race in file locking (Issue 2) | Bug | Medium |
| ASAP | Fix `is_connection_error` over-matching (Issue 3) | Bug | Low |
| ASAP | Fix non-atomic task locking (Issue 4) | Bug | Medium |
| High | Replace `time.sleep()` with async (Issue 5) | Performance | Low |
| High | Replace LRU Cache O(n) with OrderedDict (Issue 6) | Performance | Low |
| High | Replace `list.pop(0)` with deque (Issue 7) | Performance | Low |
| High | Unify response format (Issue 13) | Consistency | High |
| Medium | Migrate sync I/O in async paths (Issue 8) | Performance | High |
| Medium | Parallel context file loading (Issue 9) | Performance | Medium |
| Medium | SSRF bypass protection (Issue 10) | Security | Low |
| Medium | Path traversal protection (Issue 11) | Security | Low |
| Medium | Replace 8 TypedDict with BaseModel (V1) | Rules | Medium |
| Medium | Remove 17 type-checker suppressions (V3) | Rules | Medium |
| Medium | Implement `_migrate_doc_mcp_style` or remove (Issue 17) | Completeness | Low-Medium |
| Medium | Fix 11 silent error swallowing blocks (Issue 18) | Completeness | Medium |
| Medium | Add tests for result_links_models.py (Issue 19) | Coverage | Medium |
| Medium | Split model files with multiple public classes (Issue 14) | Rules | High |
| Low | Fix TYPE_CHECKING imports (V2) | Rules | Low |
| Low | Add subprocess timeouts (Issue 12) | Security | Low |
| Low | Pre-compile regex, set-based lookups, token cache | Performance | Low |
| Low | Refactor `get_managers` access pattern (Issue 16) | Consistency | Medium |
