# Phase 51: Just-in-Time Context with Section-Level Loading

**Status:** PENDING
**Created:** 2026-02-11
**Priority:** HIGH
**Estimated Effort:** 2 sprints
**Related:** Phase 50 (Tool Consolidation), Phase 49 (Advanced Tool Use)

## Goal

Transform Cortex's context loading from full-file dumps to a just-in-time, section-level retrieval system that returns lightweight metadata first and lets agents request specific sections on demand — following Anthropic's hybrid retrieval strategy from "Effective Context Engineering for AI Agents."

## Context

Anthropic's context engineering article advocates for a hybrid approach: "Rather than pre-processing all relevant data up front, agents maintain lightweight identifiers (file paths, stored queries, web links, etc.) and use these references to dynamically load data into context at runtime using tools."

Current Cortex `load_context` behavior:

- Returns **full file contents** for all selected memory bank files
- A typical load returns 10K-20K tokens even when only a few sections are relevant
- No ability to request individual sections (e.g., just "## Current Focus" from activeContext.md)
- Progressive loading exists but still works at file granularity, not section level

The Claude Code pattern is instructive: `CLAUDE.md` files are loaded upfront, while `glob` and `grep` let it navigate on demand. Cortex should similarly front-load essential metadata and let agents drill into specific sections.

**Reference:** <https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents>

## Approach

1. Add section-level metadata to the metadata index
2. Implement a `load_context_map` tool that returns just file/section metadata (names, headings, token counts, last-modified)
3. Implement a `read_section` tool (or parameter) that loads a specific section from a memory bank file
4. Update `load_context` to support a `depth` parameter: "metadata_only", "summary", "full"
5. Update agents/prompts to use the two-step pattern: load map → read sections

## Implementation Steps

### Step 1: Section-Level Metadata Index

- [ ] Extend MetadataIndex to store section-level information for each memory bank file:
  - Section heading (e.g., "## Current Focus")
  - Section level (h1, h2, h3)
  - Section start/end line numbers
  - Section token count
  - Section content hash (for change detection)
- [ ] Update metadata index on file write to include section data
- [ ] Add section parsing to MetadataIndex.update() using existing heading extraction
- [ ] Unit tests for section metadata extraction

### Step 2: Context Map Tool

- [ ] Create `load_context_map` tool (or add `depth="metadata_only"` to `load_context`) that returns:

  ```json
  {
    "files": [
      {
        "name": "activeContext.md",
        "total_tokens": 2500,
        "last_modified": "2026-02-11T21:00",
        "relevance_score": 0.85,
        "sections": [
          {"heading": "## Completed Work (2026-02-11)", "tokens": 1800, "level": 2},
          {"heading": "## Current Focus", "tokens": 200, "level": 2},
          {"heading": "## Next Steps", "tokens": 150, "level": 2}
        ]
      }
    ],
    "total_files": 7,
    "total_tokens_available": 15000
  }
  ```

- [ ] Context map costs ~500 tokens vs ~15000 for full load (97% reduction)
- [ ] Include relevance scores so agents can decide what to drill into
- [ ] Unit tests for context map generation

### Step 3: Section-Level Read

- [ ] Add `section` parameter to `manage_file(operation="read")`:
  - `manage_file(file_name="activeContext.md", operation="read", section="## Current Focus")`
  - Returns only the content of that section (heading + content until next heading of same/higher level)
- [ ] Support section path for nested headings: `"## Completed Work/### 2026-02-11"`
- [ ] Support multiple sections: `sections=["## Current Focus", "## Next Steps"]`
- [ ] Fallback: if section not found, return full file with a warning
- [ ] Unit tests for section extraction with various heading levels

### Step 4: load_context Depth Parameter

- [ ] Add `depth` parameter to `load_context`:
  - `"metadata_only"` — returns context map (file names, sections, token counts, relevance)
  - `"summary"` — returns first paragraph of each file + section headings
  - `"full"` — current behavior (full file contents)
- [ ] Default depth depends on token budget:
  - If budget < 5000: metadata_only
  - If budget 5000-15000: summary
  - If budget > 15000: full
- [ ] Update ContextOptimizer to support depth-aware loading
- [ ] Unit tests for each depth level

### Step 5: Hybrid Retrieval Strategy

- [ ] Implement "always-load" list: `projectBrief.md` and `activeContext.md` sections "## Current Focus" and "## Next Steps" always loaded in full (like Claude Code loads CLAUDE.md)
- [ ] Configure always-load list in optimization.json
- [ ] Everything else loaded as metadata first, full content on demand
- [ ] Update `load_context` to implement hybrid strategy:
  1. Load always-loaded files/sections in full
  2. Load metadata for everything else
  3. Agent can request specific sections via `manage_file(section=...)`

### Step 6: Update Prompts and Documentation

- [ ] Update implement-next-roadmap-step prompt to use two-step pattern:
  1. `load_context(depth="metadata_only")` to get overview
  2. `manage_file(section="...")` to drill into relevant sections
- [ ] Update AGENTS.md context loading guidance
- [ ] Update docs/api/tools.md with new parameters
- [ ] Add context loading best practices to CLAUDE.md

### Step 7: Testing and Validation

- [ ] Unit tests for all new parameters and behaviors (95%+ coverage)
- [ ] Integration test: full two-step retrieval workflow
- [ ] Measure token savings:
  - Context map vs full load (target: 90%+ reduction for metadata_only)
  - Section read vs full file (target: 70%+ reduction for single section)
- [ ] Verify no regression in task completion quality
- [ ] Performance benchmarks for section extraction

## Dependencies

- MetadataIndex (existing, needs extension)
- ContextOptimizer (existing, needs depth support)
- Phase 50 (Tool Consolidation) — complementary, response_format aligns with depth concept

## Success Criteria

1. `load_context(depth="metadata_only")` returns context map in < 500 tokens
2. Section-level `manage_file(section=...)` reads work correctly for all memory bank files
3. Hybrid strategy loads essential context + metadata for 80%+ fewer tokens than full load
4. Prompts updated to use two-step pattern
5. 95%+ test coverage for all new functionality

## Testing Strategy

- **Coverage Target:** 95%+ for all new/modified code
- **Unit Tests:** Section metadata extraction, context map generation, section-level reads, depth parameter behavior, hybrid strategy configuration
- **Integration Tests:** Full two-step workflow (load map → read section → complete task)
- **Edge Cases:** Empty sections, deeply nested headings, section not found, malformed Markdown, concurrent reads during write
- **Regression Tests:** Existing `load_context` and `manage_file` behavior unchanged when new params not used
- **AAA Pattern:** All tests follow Arrange-Act-Assert
- **Pydantic v2:** Use Pydantic models for context map and section read response validation

## Risks and Mitigation

| Risk | Impact | Mitigation |
|------|--------|------------|
| Section parsing unreliable for complex Markdown | Medium | Use well-tested heading regex, fallback to full file |
| Agents don't adopt two-step pattern | Medium | Update prompts, measure usage, provide examples |
| Metadata index size increases significantly | Low | Section metadata is small (~50 bytes per section) |
| Performance overhead of section extraction | Low | Cache section boundaries in metadata index |

## Notes

- Anthropic: "agents can assemble understanding layer by layer, maintaining only what's necessary in working memory"
- The metadata-first approach also enables better relevance scoring at section level, not just file level
- Future enhancement: semantic search over sections using embeddings
