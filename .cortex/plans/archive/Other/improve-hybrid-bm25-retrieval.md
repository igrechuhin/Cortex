---
title: "Improvement: Hybrid BM25 + Keyword Retrieval for Memory Bank Search"
component: retrieval
work_type: feature
status: PENDING
priority: Medium
created: 2026-04-14
depends_on: []
---

## Goal

Add a BM25 keyword scorer to all memory bank retrieval paths in Cortex. Currently retrieval is string-search only (grep-style). BM25 provides term-frequency / inverse-document-frequency ranking so that rare, specific terms (plan slugs, error codes, function names) score higher than common words. This improves the quality of L3 deep search, `manage_file` lookups, and any future semantic layer.

Inspired by MemPalace's `searcher.py` which combines Okapi BM25 + vector similarity to achieve 34% retrieval accuracy improvement over structure-only search.

## Context

## Current behaviour

Memory bank retrieval is currently either:

- Direct file reads (the agent reads the whole file)
- Grep-style keyword matching (substring search with no ranking)

There is no ranked retrieval. An agent searching for "FastMCP startup crash" gets all paragraphs containing any of those words, unsorted.

## Target behaviour

A `BM25Scorer` class computes Okapi BM25 scores over a corpus of text chunks. Any retrieval path can call it to get a ranked list of most-relevant paragraphs.

Key properties:

- **Pure Python, no dependencies** — no `rank_bm25`, no `sklearn`. IDF computed over the candidate set at query time (not a global index).
- **Chunk-level, not file-level** — scores individual paragraphs, not whole files.
- **Composable** — takes `list[str]` as corpus, returns `list[tuple[int, float]]` (index, score) sorted by score descending.
- **Zero side effects** — stateless function, safe to call concurrently.

## Implementation Steps

## Step 1: Implement the BM25 scorer

File: `src/cortex/retrieval/bm25.py` (new file)

1. Implement `tokenize(text: str) -> list[str]`: lowercase, split on whitespace and punctuation, remove tokens < 2 chars. No stemming — keep implementation simple.
2. Implement `bm25_scores(query: str, corpus: list[str], k1: float = 1.5, b: float = 0.75) -> list[float]`:
   - Tokenize query and all corpus documents.
   - Compute IDF over the corpus: `log((N - df + 0.5) / (df + 0.5) + 1)` for each query term.
   - Compute BM25 score for each doc: standard Okapi formula.
   - Return a list of floats parallel to `corpus`.
3. Implement `rank(query: str, corpus: list[str], top_k: int = 10) -> list[tuple[int, float]]`:
   - Calls `bm25_scores(query, corpus)`.
   - Returns `(original_index, score)` pairs sorted by score descending, top_k only.
   - Filters out zero-score results.
4. All three functions must be ≤ 30 lines each. No class needed — pure functions.
5. Add module docstring citing Okapi BM25 formula origin (Robertson & Zaragoza, 2009).

**Verification**: Unit test — corpus of 5 paragraphs, query term appears in 2; assert those 2 rank first; assert the one with higher term frequency ranks above the other.

## Step 2: Implement the memory bank chunker

File: `src/cortex/retrieval/chunker.py` (new file)

1. `chunk_markdown(text: str, source: str = "") -> list[TextChunk]`.
2. `TextChunk(BaseModel)`: `text: str`, `source: str`, `start_line: int`, `end_line: int`, `heading: str = ""`.
3. Split on blank lines (paragraph-level chunks). Minimum chunk size: 20 chars.
4. Track the most recent heading (lines starting with `#`) for each chunk.
5. Return list of `TextChunk`; empty list for empty input.
6. Keep ≤ 30 lines.

**Verification**: Unit test — markdown with 3 paragraphs under 2 headings; assert 3 chunks with correct `heading` values.

## Step 3: Implement the `MemoryBankSearcher`

File: `src/cortex/retrieval/memory_searcher.py` (new file)

1. `MemoryBankSearcher` with `__init__(project_root: Path)`.
2. `search(query: str, top_k: int = 10, file_filter: list[str] | None = None) -> list[SearchResult]`:
   - Collect all `.md` files from `.cortex/memory-bank/`, `.cortex/plans/`, `.cortex/wiki/` (filtered by `file_filter` if provided).
   - Chunk each file via `chunk_markdown(text, source=filename)`.
   - Combine all chunks into one corpus.
   - Call `rank(query, [c.text for c in corpus], top_k=top_k)`.
   - Return `list[SearchResult]` preserving chunk metadata.
3. `SearchResult(BaseModel)`: `text: str`, `source: str`, `score: float`, `heading: str`, `start_line: int`.
4. File reads are synchronous (small files, local disk). Cache file contents per search call (not across calls — no stale data risk).
5. `MemoryBankSearcher` ≤ 50 lines.

**Verification**: Integration test — `MemoryBankSearcher(project_root)` with real `.cortex/` fixtures; `search("FastMCP startup crash")` returns at least one result with `source` pointing to a real file.

## Step 4: Add `operation="search"` to `manage_file`

File: `src/cortex/tools/memory/manage_file.py` (existing)

1. Add `operation="search"` to the manage_file tool.
2. Input: `content={"query": "...", "top_k": 10, "file_filter": [...]}` (top_k and file_filter optional).
3. Instantiate `MemoryBankSearcher(project_root)` and call `.search(query, top_k, file_filter)`.
4. Return results as JSON: `[{"text": ..., "source": ..., "score": ..., "heading": ...}, ...]`.
5. Keep new handler ≤ 20 lines.

**Verification**: `manage_file(operation="search", content='{"query": "temporal memory"}')` returns non-empty ranked results.

## Step 5: Wire into L3 deep search (if layered context plan is active)

File: `src/cortex/resources/context/l3_deep_search.py` (from layered context plan)

1. If the layered context plan is active, replace its standalone BM25 implementation with `from cortex.retrieval.bm25 import rank`.
2. Use `MemoryBankSearcher` as the underlying engine for L3.
3. If layered context plan is not yet merged, skip — mark as DEFERRED.

**Verification**: L3 deep search uses the shared `bm25.py` scorer; no duplicate BM25 implementation exists.

## Step 6: Add result deduplication

File: `src/cortex/retrieval/memory_searcher.py` (same file)

1. After ranking, deduplicate by `(source, start_line)` pair — same paragraph should not appear twice even if matched by multiple query terms.
2. Add `deduplicate(results: list[SearchResult]) -> list[SearchResult]` pure function.
3. Keep ≤ 15 lines.

**Verification**: Unit test — corpus with a duplicate paragraph; assert it appears only once in results.

## Step 7: Tests

Files:

- `tests/retrieval/test_bm25.py`
- `tests/retrieval/test_chunker.py`
- `tests/retrieval/test_memory_searcher.py`
- `tests/tools/memory/test_manage_file_search.py`

1. Unit: `bm25_scores` formula correctness; `rank` top_k filter; zero-score filtering.
2. Unit: `chunk_markdown` paragraph split; heading tracking; min-size filter.
3. Integration: `MemoryBankSearcher` with fixture; query result ordering; deduplication.
4. Integration: `manage_file(operation="search")` end-to-end.

## Dependencies

- No blocking dependencies.
- Layered context plan (L3) can optionally import the shared scorer (Step 5) — not required.
- Typed memory plan can use `manage_file(operation="search", file_filter=["activeContext.md"])` for typed retrieval.

## Success Criteria

- [ ] `bm25_scores` is deterministic for identical inputs.
- [ ] `MemoryBankSearcher.search("known term")` returns the correct file as top result.
- [ ] `manage_file(operation="search")` is callable via MCP with no extra dependencies.
- [ ] Zero-score results are filtered from output.
- [ ] Deduplication prevents the same paragraph appearing twice.
- [ ] All new files ≤ 400 lines, all functions ≤ 30 lines, no `Any` types.
- [ ] 95%+ test coverage for all new modules.
- [ ] No external package dependencies beyond Python stdlib.

## Testing Strategy

- **Unit**: BM25 formula, IDF computation, top_k truncation, zero-score filter.
- **Unit**: Chunker paragraph splits, heading attribution, empty input.
- **Integration**: Real `.cortex/` fixture; verify ordering and deduplication.
- **Regression**: Existing `manage_file` operations unaffected by new `search` operation addition.
- Target: 95% line coverage for `bm25.py`, `chunker.py`, `memory_searcher.py`.
