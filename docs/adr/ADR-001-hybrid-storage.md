# ADR-001: Hybrid Storage Architecture

## Status

Accepted

## Context

Cortex needs to manage potentially hundreds of memory bank files efficiently while providing fast metadata lookups, dependency tracking, and validation capabilities. The system must handle:

1. **File Operations**: Reading, writing, and watching memory bank files stored on disk
2. **Metadata Management**: Tracking file metadata (size, hash, timestamps, dependencies)
3. **Performance**: Fast lookups for file metadata without repeatedly reading from disk
4. **Reliability**: Detecting file corruption, conflicts, and external modifications
5. **Consistency**: Maintaining synchronization between files and metadata
6. **Recovery**: Handling corrupted metadata index without data loss

The fundamental question was: Should we use pure file storage, pure database storage, or a hybrid approach?

### Requirements

**Functional Requirements**:

- Store memory bank content in human-readable, version-controllable format
- Support fast metadata queries without scanning all files
- Track dependencies between files for transclusion resolution
- Detect external file modifications made outside the system
- Recover from metadata corruption without losing file data
- Support concurrent access patterns safely

**Non-Functional Requirements**:

- Minimize dependencies (no external database servers)
- Work across all platforms (Windows, macOS, Linux)
- Support version control systems (Git) natively
- Enable manual file editing without breaking the system
- Provide subsecond metadata lookups for typical repositories
- Scale to hundreds of memory bank files

### Problem Space

**File System Characteristics**:

- ✅ Files are human-readable and editable
- ✅ Version control systems handle files natively
- ✅ No external dependencies required
- ✅ Cross-platform compatible
- ❌ Slow metadata extraction (requires reading entire files)
- ❌ No built-in indexing for fast queries
- ❌ Expensive dependency graph construction

**Database Characteristics**:

- ✅ Fast metadata queries with indexes
- ✅ Built-in query capabilities
- ✅ Transaction support for consistency
- ❌ Requires external server (SQLite is exception)
- ❌ Binary format not human-readable
- ❌ Poor version control integration
- ❌ Additional operational complexity

**Memory-Only Approach**:

- ✅ Fastest possible queries
- ✅ Simple implementation
- ❌ Data loss on crash
- ❌ Slow startup with large repositories
- ❌ High memory usage for large repositories

### Use Case Analysis

**Primary Use Cases**:

1. **File Creation/Update**: Write content to disk, update metadata index
2. **Metadata Query**: Lookup file hash, size, dependencies without reading file
3. **Dependency Resolution**: Find all files that depend on a given file
4. **Validation**: Check file integrity using cached hashes
5. **External Changes**: Detect when files are modified outside the system

**Access Patterns**:

- Metadata queries are 10-100x more frequent than file content reads
- Dependency queries happen on every transclusion resolution
- File writes are infrequent (mostly during development sessions)
- External modifications should trigger re-indexing
- System startup should be fast (<1 second for typical repositories)

## Decision

We will implement a **hybrid storage architecture** combining:

1. **Primary Storage (Files)**: Memory bank content stored as Markdown files on disk
2. **Secondary Storage (Metadata Index)**: JSON index file caching metadata and dependencies
3. **Synchronization Layer**: FileSystemManager coordinating between storage layers

### Architecture Components

**FileSystemManager** (`src/cortex/managers/file_system.py`):

- Manages all file I/O operations using `aiofiles`
- Handles file locking to prevent race conditions
- Coordinates writes to both file and metadata index
- Provides atomic operations for consistency

**MetadataIndex** (`src/cortex/core/metadata_index.py`):

- JSON file storing file metadata (`.memory-bank-index`)
- Structure: `{file_path: {hash, size, modified, dependencies, ...}}`
- Corruption detection and auto-recovery
- Incremental updates on file changes

**FileWatcher** (`src/cortex/managers/file_watcher.py`):

- Detects external file modifications
- Triggers metadata index updates
- Uses file system events where available
- Fallback to polling for unsupported platforms

### Data Flow

**Write Path**:

```
User Write Request
    ↓
FileSystemManager.write_file()
    ↓
1. Write content to disk (atomic)
2. Calculate file hash
3. Update metadata index
4. Notify FileWatcher
    ↓
Success Response
```

**Read Path**:

```
Metadata Query
    ↓
MetadataIndex.get_metadata()
    ↓
Return cached metadata (no disk I/O)
    ↓
Content Query (if needed)
    ↓
FileSystemManager.read_file()
    ↓
Read from disk + validate hash
```

**External Change Detection**:

```
File Modified Externally
    ↓
FileWatcher detects change
    ↓
FileSystemManager.refresh_metadata()
    ↓
Re-read file, update hash/metadata
    ↓
MetadataIndex updated
```

### Storage Format

**File Storage** (`.cursor/memory-bank/*.md`):

```markdown
# Project Brief

Content here...

Dependencies:
- {{include:docs/architecture.md}}
```

**Metadata Index** (`.memory-bank-index`):

```json
{
  ".cursor/memory-bank/projectBrief.md": {
    "hash": "abc123...",
    "size": 1024,
    "modified": "2024-01-10T12:00:00Z",
    "dependencies": [
      "docs/architecture.md"
    ],
    "schema_version": "1.0"
  }
}
```

### Consistency Guarantees

**Atomicity**:

- File writes use atomic operations (write to temp, then rename)
- Metadata updates are atomic (write to temp index, then rename)
- Failed writes leave previous state intact

**Durability**:

- File content is primary source of truth
- Metadata index can be rebuilt from files if corrupted
- Version control captures all file changes

**Consistency**:

- Metadata updates happen synchronously with file writes
- Hash validation detects stale metadata
- External changes trigger re-indexing

**Isolation**:

- File-level locking prevents concurrent modifications
- Metadata updates are serialized per file
- Read operations don't block other reads

## Consequences

### Positive

**1. Performance Benefits**:

- Metadata queries are O(1) lookups in JSON index (subsecond)
- No need to read/parse files for metadata extraction
- Dependency graph construction is fast (cached in index)
- Startup time remains low even with hundreds of files

**2. Developer Experience**:

- Files remain human-readable Markdown
- Direct file editing works seamlessly
- Git and other VCS tools work normally
- No database setup or maintenance required

**3. Reliability**:

- File content is always source of truth
- Metadata index can be rebuilt if corrupted
- External modifications are detected automatically
- No data loss from metadata issues

**4. Simplicity**:

- No external database dependencies
- Single JSON file for metadata (easy to understand)
- Cross-platform compatibility guaranteed
- Simple backup/restore (just copy files)

**5. Scalability**:

- Handles hundreds of files efficiently
- Incremental metadata updates (only changed files)
- Memory usage scales with number of files, not content size
- Network file systems supported (NFS, SMB)

### Negative

**1. Synchronization Complexity**:

- Must keep file system and metadata index in sync
- Race conditions possible with external modifications
- Requires careful error handling for partial failures

**2. Index Maintenance**:

- `.memory-bank-index` file must be maintained
- Index can become stale if external tools bypass FileSystemManager
- Requires corruption detection and recovery logic

**3. Startup Cost**:

- Must validate index on startup (check hashes match)
- Large repositories may require full re-index on first run
- Index corruption requires scanning all files to rebuild

**4. File Locking Overhead**:

- Locking adds slight latency to operations
- Potential contention with many concurrent writers
- Lock files must be cleaned up properly

**5. External Tool Integration**:

- External tools can create inconsistency
- FileWatcher has some latency in detecting changes
- Polling fallback is resource-intensive

### Neutral

**1. Storage Redundancy**:

- Some metadata stored in both files and index
- Trade-off: duplicated data for performance gain
- Acceptable overhead (metadata is small)

**2. Platform Dependencies**:

- File watching uses platform-specific APIs where available
- Fallback to polling on unsupported platforms
- Performance varies by platform

**3. Concurrency Model**:

- Single-writer-multiple-readers pattern
- More restrictive than multi-writer databases
- Acceptable for typical memory bank usage patterns

**4. Index Format**:

- JSON is human-readable but not optimized for large datasets
- Could migrate to binary format (SQLite) in future
- Current format is good enough for target scale

## Alternatives Considered

### Alternative 1: Pure File Storage (No Index)

**Approach**: Store everything in files, read files for all metadata queries.

**Pros**:

- Simplest implementation
- No synchronization needed
- No index corruption possible
- Minimal code complexity

**Cons**:

- Slow metadata queries (must read entire files)
- Expensive dependency graph construction
- Poor performance with large repositories
- Validation requires reading all files

**Rejection Reason**: Unacceptable performance for metadata-heavy operations like validation, dependency resolution, and quality metrics calculation. Would not scale beyond 10-20 files.

### Alternative 2: SQLite Database

**Approach**: Store metadata in SQLite database, keep files for human-readable content.

**Pros**:

- Fast queries with SQL
- Built-in indexing and transactions
- Proven reliability
- Better concurrency support

**Cons**:

- Binary format (not human-readable)
- Requires SQLite dependency
- More complex backup/restore
- Harder to debug issues
- Version control ignores database

**Rejection Reason**: Adds operational complexity and dependency without significant benefits over JSON index. SQLite is overkill for our scale (hundreds of files, not millions). JSON index provides sufficient performance.

### Alternative 3: In-Memory Only (No Persistence)

**Approach**: Keep all metadata in memory, rebuild from files on startup.

**Pros**:

- Fastest queries (no I/O)
- No synchronization issues
- Simple implementation
- No index maintenance

**Cons**:

- Data loss on crash
- Slow startup with large repositories
- High memory usage
- No persistence of learning data

**Rejection Reason**: Slow startup is unacceptable for MCP servers (should be <1 second). Learning engine requires persisting feedback data. High memory usage doesn't scale.

### Alternative 4: Git-Based Storage

**Approach**: Use Git as the storage layer, query Git for metadata.

**Pros**:

- Version control built-in
- Distributed architecture
- Mature tooling
- Audit trail for all changes

**Cons**:

- Requires Git repository
- Git operations are slow for metadata queries
- Complex API (libgit2 or subprocess calls)
- Not all use cases need version control

**Rejection Reason**: Git is too heavy for our needs. Metadata queries would require shelling out to `git` commands or using `libgit2`, both much slower than JSON lookups. Users can still use Git for version control of files.

### Alternative 5: Distributed Database (etcd, Consul)

**Approach**: Use distributed key-value store for metadata.

**Pros**:

- Distributed consistency
- High availability
- Watch capabilities
- Production-grade

**Cons**:

- Requires external server
- Network dependency
- Massive overkill for single-user tool
- Complex setup and maintenance

**Rejection Reason**: Cortex is a local tool for individual developers, not a distributed system. Requiring a separate server would be completely impractical.

### Alternative 6: Full-Text Search Engine (Elasticsearch, Meilisearch)

**Approach**: Index all content in search engine for fast queries.

**Pros**:

- Extremely fast full-text search
- Advanced query capabilities
- Faceting and aggregations
- Scalable to millions of documents

**Cons**:

- Requires external server
- Complex setup
- Overkill for metadata queries
- High resource usage

**Rejection Reason**: We don't need full-text search capabilities (basic grep is sufficient). The overhead of running a search engine is unjustifiable for our use case.

## Implementation Notes

### Migration Path

If the hybrid approach proves insufficient, migration paths exist:

1. **To SQLite**: Convert JSON index to SQLite database (backwards compatible)
2. **To In-Memory**: Remove persistence, rebuild on startup (simplification)
3. **To Pure Files**: Remove index, read from files (simplification)

The file-first design ensures we're never locked into the metadata index format.

### Performance Targets

Based on typical memory bank usage:

- Metadata query: <1ms (in-memory JSON lookup)
- File read: <10ms (disk I/O)
- File write: <50ms (disk I/O + index update)
- Full validation: <100ms for 50 files
- Dependency resolution: <5ms for typical transclusion tree

### Monitoring

Track these metrics to validate the decision:

- Metadata index hit rate (should be >99%)
- Index rebuild frequency (should be rare)
- Synchronization errors (should be near zero)
- Startup time (should be <1 second)

### Future Optimizations

Possible improvements if needed:

1. **Incremental startup**: Lazy-load metadata index entries
2. **Index sharding**: Split index by directory for large repositories
3. **Compression**: Compress index file for large metadata sets
4. **SQLite migration**: Move to SQLite if JSON performance insufficient

## References

- [Cline Memory Bank Pattern](https://docs.cline.bot/improving-your-prompting-skills/cline-memory-bank)
- [LMAX Disruptor Pattern](https://lmax-exchange.github.io/disruptor/): High-performance in-memory event processing
- [Log-Structured Merge Tree](https://en.wikipedia.org/wiki/Log-structured_merge-tree): Write-optimized storage
- [SQLite Use Cases](https://www.sqlite.org/whentouse.html): When SQLite is appropriate vs overkill

## Related ADRs

- ADR-003: Lazy Manager Initialization - How managers are initialized
- ADR-006: Async-First Design - Async file I/O patterns
- ADR-008: Security Model - Path traversal protection

## Revision History

- 2024-01-10: Initial version (accepted)
