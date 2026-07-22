<!-- memory_type: preference -->
# System Patterns: Cortex

**Schema Extension Note**: This file has schema validation with required sections (`## System Architecture`/`## Architecture`, `## Design Patterns`/`## Design Patterns in Use`, `## Component Relationships`). When adding new content, maintain proper heading hierarchy (H2 → H3 → H4, max 3 levels) and do not skip heading levels. See `memory-bank-workflow.mdc` for detailed extension guidance.

## Architecture

Cortex is structured as an MCP (Model Context Protocol) server with a modular, layered architecture:

- **Layer 1: MCP Server** - Entry point with tools across phases
- **Layer 2: Tool Modules** - Phase-specific tool implementations
- **Layer 3: Manager Initialization** - Centralized lifecycle management with dependency injection
- **Layer 4: Business Logic** - Modules with single responsibilities
- **Layer 5: Storage** - Git-tracked files and metadata indexes

## Key Technical Decisions

- **Protocol-Based Architecture** - PEP 544 structural subtyping for loose coupling
- **Dependency Injection** - All managers receive dependencies via constructor
- **Async Throughout** - All I/O operations use async/await with aiofiles
- **Lazy Initialization** - Managers initialized only when first requested
- **File Locking** - Prevents concurrent write conflicts
- **Version History** - Automatic snapshots for rollback capability

## Design Patterns

- **Dependency Injection** - All external dependencies injected via constructors
- **Protocol-Based Abstractions** - Structural subtyping for testability
- **Manager Pattern** - Centralized service management via ManagerContainer
- **Template Method** - Standardized tool response patterns
- **Strategy Pattern** - Multiple loading strategies (dependency-aware, by-relevance, etc.)
- **Observer Pattern** - File watching for external change detection
- **Language-Agnostic Script Pattern** - All procedures use scripts from the Synapse scripts directory (path resolved via project structure or Cortex tools) instead of hardcoded commands
- **Semantic Names and Cortex Tools** - Prompts and procedures use semantic names ("plans directory", "memory bank", "Synapse agents directory") and resolve paths via Cortex MCP tools (`get_structure_info()`, `manage_file()`, `rules()`); hardcoding `.cortex/` or `.cursor/` paths is forbidden
- **Cursor-Agent Delegation Pattern** - Top-level prompts (`commit.md`, `do.md`) are thin orchestrators; all substantive logic lives in named cursor-agents (`commit-preflight`, `commit-checks`, `commit-docs`, `commit-validate`, `commit-final-gate`, `implement-select`, `implement-code`, `implement-finalize`, `implement-verify`). Agents are auto-synced from `.cortex/synapse/cursor-agents/` to `.cursor/agents/` on every MCP startup via `sync_cursor_agents()`. Presence enforced by `TestRequiredAgentFilesPresent`.
- **Zero-Arg Quality Gate Pattern** - Long-running quality checks use `run_quality_gate()` (Phase A), `run_docs_gate()` (Phase B), and `autofix()`. These zero-arg tools spawn detached subprocesses with heartbeat polling internally, avoiding MCP `-32000` connection-closed timeouts. Legacy `start_quality_job`/`get_quality_job_status`/`execute_pre_commit_checks` are deprecated (sunset 2026-07-01); migrate all callers to zero-arg tools.
- **Shared-Defaults Reference** - Quality thresholds (30 lines/fn, 400 lines/file, 90%/95% coverage, 3 fix iterations) are declared once in `cursor-agents/shared-defaults.md`. Individual agents cite this file instead of hardcoding numbers. Projects using Cortex MCP can override thresholds via their `rules()` configuration.
- **Experience Store Pattern (Trellis-style)** - `src/cortex/experience/` persists pipeline search history to `.cortex/experience/experience.db` (SQLite, WAL journal mode) using the Trellis hierarchy: `tasks` (spec + success metric) → `sessions` (one per `CORTEX_SESSION_ID` × pipeline, deterministic ids) → `nodes` (one per phase transition/gate run, with `parent_id` lineage, `step_number`, `status`, `fitness`, `artifact_ref`). Pydantic 2 models (`ExperienceTask`, `ExperienceSession`, `ExperienceNode`) back a sync `ExperienceStoreCore` (mirrors `TemporalMemoryStore` sqlite3 conventions) plus an async `ExperienceStore` facade (`asyncio.to_thread`). Instrumentation: `pipeline_handoff` `op_mark_running`/`op_write_result` record one node per phase event; `run_quality_gate()` result handling (`record_gate_result` in `experience/gate_hook.py`) attaches gate pass/fail as node fitness (1.0/0.0) with a score-summary artifact under `.cortex/experience/artifacts/`. Recording is best-effort: disabled via `CORTEX_EXPERIENCE_RECORDING=0`, failures logged at WARNING with the session id as trace id and counted (`recording_failure_count()`), and never abort a pipeline.
- **Vector-Seeded Experience Recall Pattern** - `src/cortex/experience/encoder.py` defines a sync `EncoderProtocol` (dependency-injected); the default `HashingEncoder` is a local feature-hashing (Weinberger et al. 2009) bag-of-words embedding — deterministic, no external API, no heavyweight ML dependency — producing L2-normalized vectors scored by cosine similarity (`embedding_math.py`). `EmbeddingIndexCore`/`EmbeddingIndex` (sync core + `asyncio.to_thread` async facade, mirroring `ExperienceStoreCore`/`ExperienceStore`) persist vectors as BLOBs in a `task_embeddings` table in the same `experience.db`, with brute-force top-k cosine scan (acceptable at dev-tool scale). `recorder.py`'s `_ensure_lineage` embeds and upserts every recorded task's spec exactly once per creation path (idempotent upsert). `recall.py`'s `recall_similar_tasks()` vector-searches a widened candidate pool, then `hybrid_rank.py` re-scores candidates by combining vector similarity with BM25 (`retrieval/bm25.py`) over the same task-spec corpus, and walks each match's node graph for its highest-fitness outcome and any repeated-failure (`>=2x` FAILED same label) "dead end". `recall_render.py` renders a compact, whole-line-truncated summary within a configured character budget. `tools/session/experience_recall_brief.py` merges this into `SessionBrief.experience_recall_summary` (capped again in `brief_cap.py`) using the session's primary goal (falling back to `current_focus`); disabled via `ProjectSessionConfig.experience_recall_enabled` (`.cortex/session.yaml`) or absent goal/store, in which case the field stays `None` and is omitted from `session()` JSON (`exclude_none=True`), preserving pre-feature output byte-for-byte.
- **Synapse Rule Provenance Pattern** - `rule_provenance` table (same `experience.db`, schema version 2) links a Synapse rule id to the experience-store node pairs (failure → fix) that justify it, without touching the Synapse submodule's rule-file normative content. `src/cortex/experience/rule_provenance.py` (pure aggregation/staleness) and `rule_provenance_queries.py` (SQL) back new `ExperienceStoreCore`/`ExperienceStore` methods — `record_rule_provenance`, `refresh_rule_matches`, `rule_evidence` (the "why does this rule exist" read API), `pruning_candidates` (rules whose cited failure class had zero matches within a configurable window, default 90 days) — exposed as 4 `pipeline_handoff` operations. `analyze-session.md`/`analyze-compact.md` call these when accepting a graph-sourced rule recommendation (`record_rule_provenance` after `write_artifact`) and report staleness (`pruning_candidates` → "Rule Provenance & Pruning Candidates" report section); pruning stays a human decision, never automatic.

## Synapse Architecture (CRITICAL)

Synapse is a git submodule (Synapse directory) providing shared resources with a strict separation of concerns.

### Directory Structure (Semantic Names)

- **Synapse prompts directory** – Language-AGNOSTIC workflow definitions
- **Synapse rules directory** – Coding standards (general + language-specific)
- **Synapse scripts directory** – Language-SPECIFIC implementations (`{language}/` e.g. python/, typescript/)

Resolve actual paths via `get_structure_info()` where available; do not hardcode `.cortex/synapse/` in prompts.

### Coding Standards Ownership

**Pydantic 2 Standards**: Pydantic 2 standards are owned by Synapse and defined in `python-pydantic-standards.mdc` (Synapse rules directory). Do not duplicate Pydantic guidance in project-local documentation (techContext.md, systemPatterns.md). Instead, reference the Synapse rule via `rules(operation="get_relevant", task_description="Pydantic 2 standards")` or `get_synapse_rules(task_description="Pydantic 2")`.

### Prompts: Language-AGNOSTIC (MANDATORY)

All prompts in the Synapse prompts directory MUST be language-agnostic:

- **DO NOT** hardcode language-specific commands (`ruff`, `black`, `prettier`, `eslint`)
- **DO NOT** hardcode structure paths (use semantic names and Cortex tools)
- **DO** use semantic names ("Synapse scripts directory", "plans directory", "memory bank") and Cortex MCP tools (`get_structure_info()`, `manage_file()`, `rules()`) to resolve paths and access content

**Correct Pattern**:

- Use Cortex MCP zero-arg tools (`run_quality_gate()`, `autofix()`, `run_docs_gate()`), or reference "Synapse scripts directory" and language-specific script name (path resolved by tool or project structure).

**Wrong Pattern**:

- Hardcoding paths like `.cortex/synapse/scripts/` or commands like `.venv/bin/black --check src/ tests/`

### Scripts: Language-SPECIFIC

Scripts in `scripts/{language}/` contain language-specific implementations:

- Each language has its own directory (`scripts/python/`, `scripts/typescript/`)
- Scripts auto-detect project structure and appropriate tools
- Scripts handle environment differences (.venv, uv, npm, etc.)
- Scripts return proper exit codes and clear output

### Available Python Scripts

| Script | Purpose |
|--------|---------|
| `check_formatting.py` | Verify formatting (black --check) |
| `fix_formatting.py` | Auto-fix formatting (black) |
| `check_linting.py` | Lint checking (ruff check) |
| `check_types.py` | Type checking (pyright) |
| `check_file_sizes.py` | Verify files ≤ 400 lines |
| `check_function_lengths.py` | Verify functions ≤ 30 lines |
| `run_tests.py` | Run tests with coverage |

### Violation Examples to Avoid

- Hardcoding `black`, `ruff`, `pyright`, `prettier`, `eslint` commands in prompts
- Using language-specific paths like `src/`, `tests/` without script abstraction
- Writing procedures that assume Python/TypeScript/etc.
- Including language-specific examples in general procedures

## Component Relationships

### Core Services Stack (Initialization Order)

1. FileSystemManager → File I/O, locking, hashing
2. MetadataIndex → JSON index for file metadata
3. TokenCounter → tiktoken integration
4. DependencyGraph → Static and dynamic dependency tracking
5. VersionManager → Snapshots and version history
6. LinkParser → Parse links and transclusions
7. TransclusionEngine → Resolve `{{include:}}` references
8. SchemaValidator → File schema validation
9. QualityMetrics → Calculate quality scores
10. ContextOptimizer → Optimize context within token budgets

### Module Dependencies

- **Phase 1 (Foundation)**: FileSystemManager, MetadataIndex, TokenCounter, DependencyGraph
- **Phase 2 (Linking)**: Depends on Phase 1, adds LinkParser, TransclusionEngine
- **Phase 3 (Validation)**: Depends on Phase 1-2, adds SchemaValidator, QualityMetrics
- **Phase 4 (Optimization)**: Depends on Phase 1-3, adds RelevanceScorer, ContextOptimizer
- **Phase 5 (Analysis/Refactoring)**: Depends on Phase 1-4, adds PatternAnalyzer, RefactoringEngine

## Critical Implementation Paths

1. **File Operations** - All file operations go through FileSystemManager with locking
2. **Context Loading** - Progressive loading with token budget management
3. **Transclusion Resolution** - Recursive resolution with cycle detection
4. **Validation Pipeline** - Schema → Duplication → Quality metrics
5. **Refactoring Execution** - Approval → Validation → Execution → Rollback capability

## Error Handling Patterns

- Domain-specific exceptions with actionable error messages
- File locking prevents concurrent write conflicts
- Version snapshots enable safe rollback
- Metadata index corruption recovery
- Path validation prevents traversal attacks

## Performance Optimizations

- Lazy initialization of managers
- Caching of parsed content and metadata
- Efficient token counting with tiktoken
- Optimized dependency graph algorithms (BFS, DFS, cycle detection)
- Progressive loading to minimize token usage
