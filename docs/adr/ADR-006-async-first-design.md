# ADR-006: Async-First Design

## Status

Accepted

## Context

Cortex performs extensive I/O operations:

1. **File System I/O**: Reading, writing, watching memory bank files
2. **Network I/O**: Potential future cloud storage backends
3. **Database I/O**: Metadata index operations
4. **External Process I/O**: Git operations, linters, formatters

These I/O operations are inherently blocking. The question is: How should we handle I/O to maximize performance and user experience?

### The Synchronous Problem

**Traditional Synchronous Approach**:

```python
def validate_memory_bank():
    """Validate all files (synchronous)."""
    errors = {}
    files = list_files(".cursor/memory-bank")  # Blocking I/O

    for file in files:  # Sequential processing
        content = read_file(file)  # Blocking I/O
        errors[file] = validate(content)  # CPU-bound

    return errors  # Total time: N * (read_time + validate_time)
```

**Problems**:

1. **Sequential Processing**: Each file processed one at a time
2. **I/O Waiting**: CPU idle while waiting for disk
3. **Poor Performance**: Total time scales linearly with file count
4. **Blocking**: Server unresponsive during long operations
5. **No Concurrency**: Can't process multiple requests simultaneously

**Example Timing** (50 files):

```text
Sequential:
  Read file 1: 10ms  ┌──┐
  Validate 1:  5ms   ├─┐
  Read file 2: 10ms  ├──┐
  Validate 2:  5ms   ├─┐
  ... (50 times)
  Total: 750ms       └──────────────────────────────┘

Concurrent:
  Read all files (parallel): 50ms  ┌──────┐
  Validate all (parallel):   20ms  ├───┐
  Total: 70ms                       └────────┘

10x speedup!
```

### MCP Server Requirements

**MCP Protocol Characteristics**:

- JSON-RPC over stdio/SSE/WebSocket
- Asynchronous message passing
- Multiple concurrent requests possible
- Long-running operations should not block
- Server must remain responsive

**User Experience Requirements**:

- Fast response times (<100ms for simple operations)
- Responsive during long operations (progress updates)
- No "hanging" or unresponsive behavior
- Support concurrent operations from multiple users (future)

### Python Async/Await

Python 3.5+ provides async/await syntax for asynchronous programming:

**Async Function**:

```python
async def read_file(path: str) -> str:
    """Asynchronous file read."""
    async with aiofiles.open(path, "r") as f:
        return await f.read()
```

**Concurrent Execution**:

```python
async def read_multiple_files(paths: list[str]) -> list[str]:
    """Read multiple files concurrently."""
    return await asyncio.gather(*[
        read_file(path) for path in paths
    ])
```

**Benefits**:

- Non-blocking I/O operations
- Concurrent execution with single thread
- Cooperative multitasking (explicit await points)
- Efficient for I/O-bound workloads

### Design Space

### Option 1: Fully Synchronous

- All operations blocking
- Simple to implement
- Poor performance
- Poor UX

### Option 2: Threading

- OS threads for concurrency
- More complex (locks, race conditions)
- Higher overhead (thread switching)
- GIL limits CPU parallelism

### Option 3: Multiprocessing

- Separate processes
- True parallelism
- High overhead (IPC, serialization)
- Complex state management

### Option 4: Async/Await

- Single-threaded concurrency
- Non-blocking I/O
- Cooperative multitasking
- Modern Python standard

### Option 5: Hybrid

- Async for I/O
- Threads/processes for CPU-bound work
- Complexity managing both
- Best performance for mixed workloads

### Requirements

**Functional Requirements**:

- Support concurrent file operations
- Support concurrent validation/analysis
- Non-blocking I/O operations
- Responsive during long operations
- Handle multiple MCP requests concurrently

**Non-Functional Requirements**:

- Fast response times (<100ms for simple ops)
- Efficient resource usage (memory, CPU)
- No deadlocks or race conditions
- Clear error handling
- Type-safe async code

**Constraints**:

- Python 3.13+ target
- MCP SDK is async-based
- Must integrate with aiofiles, aiohttp
- No external event loop library (use asyncio)

## Decision

We will adopt an **async-first design** where:

1. **All I/O operations are async**: File system, network, database
2. **Public APIs are async**: All MCP tools return coroutines
3. **Concurrency by default**: Use `asyncio.gather()` for parallel operations
4. **Single event loop**: Run everything on asyncio event loop
5. **CPU-bound work handled appropriately**: Use `asyncio.to_thread()` when needed

### Architecture

**Core Principle**: If it touches I/O, it must be async.

**Async Layers**:

```text
MCP Server (async)
    ↓
Tool Handlers (async)
    ↓
Managers (async)
    ↓
I/O Operations (async)
```

**All async, all the way down.**

### Implementation Patterns

### Pattern 1: Async File I/O

```python
import aiofiles
from pathlib import Path

class FileSystemManager:
    """Async file system operations."""

    async def read_file(self, path: str) -> str:
        """Read file asynchronously."""
        async with aiofiles.open(path, "r", encoding="utf-8") as f:
            return await f.read()

    async def write_file(self, path: str, content: str) -> None:
        """Write file asynchronously."""
        async with aiofiles.open(path, "w", encoding="utf-8") as f:
            await f.write(content)

    async def list_files(self, directory: str) -> list[str]:
        """List files asynchronously."""
        path = Path(directory)
        # Path operations are sync (filesystem metadata)
        # But we can use asyncio.to_thread for consistency
        return await asyncio.to_thread(
            lambda: [str(p) for p in path.rglob("*.md")]
        )
```

### Pattern 2: Concurrent Operations with gather()

```python
async def validate_all_files(files: list[str]) -> dict[str, list[ValidationError]]:
    """Validate multiple files concurrently."""
    # Validate all files in parallel
    results = await asyncio.gather(*[
        validate_file(file) for file in files
    ], return_exceptions=True)

    # Combine results
    errors = {}
    for file, result in zip(files, results):
        if isinstance(result, Exception):
            errors[file] = [ValidationError(str(result))]
        else:
            errors[file] = result

    return errors
```

### Pattern 3: Rate Limiting with Semaphore

```python
async def read_files_with_limit(
    files: list[str],
    max_concurrent: int = 10
) -> list[str]:
    """Read files with concurrency limit."""
    semaphore = asyncio.Semaphore(max_concurrent)

    async def read_with_semaphore(file: str) -> str:
        async with semaphore:
            return await read_file(file)

    return await asyncio.gather(*[
        read_with_semaphore(file) for file in files
    ])
```

### Pattern 4: Timeout Support

```python
async def validate_with_timeout(
    file: str,
    timeout: float = 30.0
) -> list[ValidationError]:
    """Validate with timeout."""
    async with asyncio.timeout(timeout):
        return await validate_file(file)
```

### Pattern 5: CPU-Bound Work

```python
async def analyze_patterns(content: str) -> list[Pattern]:
    """Analyze patterns (CPU-bound)."""
    # Run CPU-bound work in thread pool
    return await asyncio.to_thread(
        _analyze_patterns_sync,
        content
    )

def _analyze_patterns_sync(content: str) -> list[Pattern]:
    """Synchronous pattern analysis."""
    # CPU-intensive regex matching, parsing, etc.
    patterns = []
    for pattern in PATTERNS:
        if pattern.regex.search(content):
            patterns.append(pattern)
    return patterns
```

### Pattern 6: Progress Reporting

```python
async def validate_with_progress(
    files: list[str],
    on_progress: Callable[[int, int], None] | None = None
) -> dict[str, list[ValidationError]]:
    """Validate with progress callback."""
    errors = {}
    for i, file in enumerate(files):
        errors[file] = await validate_file(file)
        if on_progress:
            on_progress(i + 1, len(files))
    return errors
```

### Pattern 7: TaskGroup for Structured Concurrency

```python
async def process_files_structured(files: list[str]) -> dict[str, object]:
    """Process files with structured concurrency."""
    results = {}

    async with asyncio.TaskGroup() as group:
        tasks = {
            file: group.create_task(process_file(file))
            for file in files
        }

    # All tasks completed (or one raised exception)
    for file, task in tasks.items():
        results[file] = task.result()

    return results
```

### MCP Tool Implementation

**Async Tool Handler**:

```python
import mcp.server.stdio as mcp

@mcp.tool()
async def validate_memory_bank() -> dict[str, object]:
    """Validate memory bank files.

    Returns:
        Validation results for all files.
    """
    # Get managers (lazy initialization)
    managers = await get_managers()
    fs = managers["file_system"]
    validator = managers["schema_validator"]

    # List all files
    files = await fs.list_files(".cursor/memory-bank")

    # Validate concurrently
    results = await asyncio.gather(*[
        validator.validate_file(file) for file in files
    ])

    # Return results
    return {
        "files_validated": len(files),
        "errors": {
            file: errors
            for file, errors in zip(files, results)
            if errors
        },
        "success": all(not errors for errors in results)
    }
```

**Server Main Loop**:

```python
async def main():
    """Run MCP server."""
    async with mcp.server() as server:
        # Initialize server (fast)
        await initialize_server()

        # Run server (handles requests asynchronously)
        await server.run()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
```

### Error Handling

### Pattern 1: Try-Except in Async

```python
async def read_file_safe(path: str) -> str | None:
    """Read file with error handling."""
    try:
        async with aiofiles.open(path, "r") as f:
            return await f.read()
    except FileNotFoundError:
        logger.warning(f"File not found: {path}")
        return None
    except Exception as e:
        logger.error(f"Error reading {path}: {e}")
        raise
```

### Pattern 2: Exception Groups (Python 3.11+)

```python
async def validate_all_with_exceptions(files: list[str]) -> dict[str, object]:
    """Validate with exception grouping."""
    try:
        async with asyncio.TaskGroup() as group:
            tasks = [
                group.create_task(validate_file(file))
                for file in files
            ]
    except* ValidationError as eg:
        # Handle validation errors
        logger.warning(f"Validation errors: {eg.exceptions}")
    except* IOError as eg:
        # Handle I/O errors
        logger.error(f"I/O errors: {eg.exceptions}")
        raise
```

### Pattern 3: Graceful Degradation

```python
async def get_file_metadata_best_effort(
    files: list[str]
) -> dict[str, dict[str, object]]:
    """Get metadata, skipping failed files."""
    results = await asyncio.gather(*[
        get_file_metadata(file)
        for file in files
    ], return_exceptions=True)

    metadata = {}
    for file, result in zip(files, results):
        if isinstance(result, Exception):
            logger.warning(f"Failed to get metadata for {file}: {result}")
            continue
        metadata[file] = result

    return metadata
```

### Performance Optimizations

### Optimization 1: Batching

```python
async def process_in_batches(
    items: list[str],
    batch_size: int = 10
) -> list[object]:
    """Process items in batches."""
    results = []
    for i in range(0, len(items), batch_size):
        batch = items[i:i + batch_size]
        batch_results = await asyncio.gather(*[
            process_item(item) for item in batch
        ])
        results.extend(batch_results)
    return results
```

### Optimization 2: Caching

```python
from functools import lru_cache

class FileSystemManager:
    def __init__(self):
        self._cache: dict[str, tuple[str, float]] = {}

    async def read_file_cached(self, path: str) -> str:
        """Read file with caching."""
        mtime = await asyncio.to_thread(lambda: Path(path).stat().st_mtime)

        # Check cache
        if path in self._cache:
            content, cached_mtime = self._cache[path]
            if mtime == cached_mtime:
                return content

        # Read and cache
        content = await self.read_file(path)
        self._cache[path] = (content, mtime)
        return content
```

### Optimization 3: Lazy Evaluation

```python
async def get_file_list_lazy(directory: str) -> AsyncIterator[str]:
    """Yield files lazily."""
    for path in Path(directory).rglob("*.md"):
        yield str(path)
        await asyncio.sleep(0)  # Yield control

# Usage
async for file in get_file_list_lazy(".cursor/memory-bank"):
    await process_file(file)
```

## Consequences

### Positive

**1. Performance**:

- 10-100x speedup for I/O-bound operations
- Concurrent file processing
- Non-blocking operations
- Efficient resource utilization

**2. Scalability**:

- Handle multiple concurrent requests
- Single thread handles thousands of connections
- No thread pool overhead
- Memory efficient

**3. Responsiveness**:

- Server never blocks
- Progress updates possible
- Cancellation support
- Better user experience

**4. Modern Python**:

- Leverages Python 3.13+ features
- Standard library support (asyncio)
- Rich ecosystem (aiofiles, aiohttp)
- Future-proof

**5. Type Safety**:

- Async functions clearly marked
- Type checkers understand async/await
- Coroutine types distinct from regular functions
- Compile-time detection of sync/async mixing

**6. Debugging**:

- Stack traces show async context
- asyncio debug mode available
- Clear await points
- No thread synchronization bugs

### Negative

**1. Complexity**:

- Learning curve for async/await
- Must understand event loop
- Async/sync boundaries tricky
- "Async infection" (all callers must be async)

**2. Ecosystem Gaps**:

- Not all libraries support async
- Must find async alternatives (aiofiles vs open)
- Sync libraries require `asyncio.to_thread()`
- Testing libraries may lack async support

**3. Debugging Challenges**:

- Asyncio stack traces can be long
- Concurrent bugs harder to reproduce
- Race conditions still possible
- Performance profiling more complex

**4. Error Handling**:

- Exception handling in gather() tricky
- CancelledError must be handled
- Timeouts add complexity
- Exception groups new (Python 3.11+)

**5. Testing Complexity**:

- Tests must be async
- Requires pytest-asyncio or similar
- Mocking async functions different
- Time-based tests harder

**6. Lock-In**:

- Committed to async all the way down
- Hard to mix sync and async
- All dependencies must support async
- Migration from sync to async difficult

### Neutral

**1. Single-Threaded**:

- No thread synchronization needed
- But also no true parallelism
- Good for I/O-bound (our use case)
- Not ideal for CPU-bound work

**2. Event Loop**:

- Single event loop simplifies reasoning
- But event loop must be managed
- Blocking operations block everything
- Must be careful about long operations

**3. Async vs Threads**:

- Async is better for I/O-bound
- Threads better for CPU-bound
- We use hybrid approach
- Context-dependent choice

## Alternatives Considered

### Alternative 1: Fully Synchronous

**Approach**: All operations blocking/synchronous.

**Pros**:

- Simple to implement
- No async complexity
- Easy to test
- Familiar to all developers

**Cons**:

- Poor performance (no concurrency)
- Blocking operations
- Unresponsive server
- Doesn't scale

**Rejection Reason**: Unacceptable performance. MCP requires non-blocking operations.

### Alternative 2: Threading

**Approach**: Use OS threads for concurrency.

```python
import concurrent.futures

def validate_memory_bank() -> dict[str, object]:
    with concurrent.futures.ThreadPoolExecutor() as executor:
        futures = [
            executor.submit(validate_file, file)
            for file in files
        ]
        results = [f.result() for f in futures]
    return results
```

**Pros**:

- True parallelism (for CPU-bound)
- Simple mental model
- No event loop
- Works with sync libraries

**Cons**:

- GIL limits parallelism
- Higher overhead (context switching)
- Race conditions (need locks)
- Thread pool management
- Not ideal for I/O-bound work

**Rejection Reason**: Async is better for I/O-bound workloads (our use case). Threading adds complexity without benefits.

### Alternative 3: Multiprocessing

**Approach**: Use separate processes for parallelism.

```python
import multiprocessing

def validate_memory_bank() -> dict[str, object]:
    with multiprocessing.Pool() as pool:
        results = pool.map(validate_file, files)
    return results
```

**Pros**:

- True parallelism (no GIL)
- Better for CPU-bound work
- Process isolation

**Cons**:

- High overhead (IPC, serialization)
- Complex state management
- Hard to share data
- Memory overhead (process copies)
- Overkill for I/O-bound work

**Rejection Reason**: Massive overkill for I/O operations. High overhead unacceptable.

### Alternative 4: Gevent (Greenlets)

**Approach**: Use gevent for cooperative concurrency.

```python
import gevent
from gevent import monkey
monkey.patch_all()

def validate_memory_bank() -> dict[str, object]:
    greenlets = [
        gevent.spawn(validate_file, file)
        for file in files
    ]
    gevent.joinall(greenlets)
    return [g.value for g in greenlets]
```

**Pros**:

- Cooperative concurrency
- Works with sync libraries (monkey patching)
- Familiar sync syntax
- Good performance

**Cons**:

- Monkey patching risky
- Not standard library
- Type checkers don't understand
- Incompatible with asyncio
- Maintenance concerns

**Rejection Reason**: Monkey patching is fragile. asyncio is standard library and better supported.

### Alternative 5: Twisted

**Approach**: Use Twisted framework.

**Pros**:

- Mature async framework
- Rich ecosystem
- Battle-tested
- Good performance

**Cons**:

- Complex API
- Different from asyncio
- Callback-based (harder to read)
- Heavy dependency
- Not standard library

**Rejection Reason**: asyncio is standard library. Twisted's callback style is harder to read than async/await.

### Alternative 6: Sync with Background Tasks

**Approach**: Synchronous API with background task queue.

```python
def validate_memory_bank() -> str:
    """Queue validation task."""
    task_id = queue.enqueue(validate_all_files)
    return task_id

def get_validation_status(task_id: str) -> dict[str, object]:
    """Get task status."""
    return queue.get_result(task_id)
```

**Pros**:

- Simple synchronous API
- Background processing
- Doesn't block
- Familiar pattern

**Cons**:

- Requires task queue infrastructure
- More complex architecture
- Polling needed for results
- State management complexity
- Not suitable for MCP protocol

**Rejection Reason**: MCP protocol is inherently async. Adding task queue is unnecessary complexity.

## Implementation Notes

### Migration from Sync to Async

**Step 1**: Identify I/O operations
**Step 2**: Add `async` keyword to functions
**Step 3**: Replace sync I/O with async I/O
**Step 4**: Add `await` to function calls
**Step 5**: Update tests to async
**Step 6**: Run type checker to find missed conversions

### Testing Async Code

**Pytest with pytest-asyncio**:

```python
import pytest

@pytest.mark.asyncio
async def test_read_file():
    """Test async file reading."""
    fs = FileSystemManager()
    content = await fs.read_file("test.md")
    assert content == "expected content"
```

**Mocking Async Functions**:

```python
from unittest.mock import AsyncMock

async def test_with_mock():
    """Test with async mock."""
    fs = AsyncMock()
    fs.read_file.return_value = "mocked content"

    content = await fs.read_file("test.md")
    assert content == "mocked content"
    fs.read_file.assert_called_once_with("test.md")
```

### Performance Monitoring

```python
import time

async def timed_operation(name: str, coro):
    """Time async operation."""
    start = time.monotonic()
    result = await coro
    elapsed = time.monotonic() - start
    logger.info(f"{name} took {elapsed:.3f}s")
    return result
```

### Best Practices

1. **Always use async I/O libraries**: aiofiles, aiohttp, asyncpg
2. **Use gather() for concurrent operations**: Don't await in loops
3. **Use TaskGroup for structured concurrency**: Cleaner than gather
4. **Use timeout() for timeouts**: Better than wait_for
5. **Handle CancelledError**: Operations may be cancelled
6. **Avoid blocking operations**: Use to_thread() if needed
7. **Keep event loop responsive**: Yield control regularly

## References

- [asyncio Documentation](https://docs.python.org/3/library/asyncio.html)
- [PEP 492: Coroutines with async/await](https://peps.python.org/pep-0492/)
- [aiofiles](https://github.com/Tinche/aiofiles)
- [AsyncIO Design Patterns](https://python.readthedocs.io/en/stable/library/asyncio-task.html)
- [Structured Concurrency](https://vorpus.org/blog/notes-on-structured-concurrency-or-go-statement-considered-harmful/)

## Related ADRs

- ADR-001: Hybrid Storage - Async file operations
- ADR-003: Lazy Manager Initialization - Async initialization
- ADR-004: Protocol-Based Architecture - Async protocols

## Revision History

- 2024-01-10: Initial version (accepted)
