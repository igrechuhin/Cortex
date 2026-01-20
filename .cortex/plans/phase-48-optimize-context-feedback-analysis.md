# Phase 48: Improve optimize_context with Session Feedback Analysis

## Status

**PLANNING** (2026-01-19)

## Goal

Create an end-of-session prompt that analyzes `optimize_context` effectiveness and provides structured feedback to improve future context optimization based on real-world usage patterns.

## Context

The `optimize_context` MCP tool selects files and sections for context based on task descriptions and relevance scoring. However, there's no feedback loop to understand:

- Whether the selected context was actually useful
- Which files were provided but never used (over-provisioning)
- Which files were needed but not provided (under-provisioning)
- How accurate the relevance scores were

This plan creates a feedback mechanism to collect real-world usage data and improve context optimization over time.

## Approach

Create an analysis prompt (`analyze-context-effectiveness.md`) that:

1. Guides the AI to recall `optimize_context` calls from the session
2. Analyzes what context was actually used during the session
3. Calculates effectiveness metrics (precision, recall, token efficiency)
4. Provides structured feedback that can be stored and used for improvement

## Implementation Steps

### Step 1: Create Analysis Prompt

Create `.cortex/synapse/prompts/analyze-context-effectiveness.md` with:

- Pre-analysis checklist for recalling optimize_context calls
- Usage analysis instructions (files read, modified, mentioned)
- Scoring metrics definitions
- Structured output format
- Integration with Cortex MCP tools for feedback storage

### Step 2: Define Scoring Metrics

Implement the following metrics:

- **Precision**: `files_used / files_provided` (higher = less waste)
- **Recall**: `files_used / files_needed` (higher = better coverage)
- **F1 Score**: Harmonic mean of precision and recall
- **Token Efficiency**: `useful_tokens / total_tokens_provided`
- **Relevance Accuracy**: Correlation between relevance scores and actual usage

### Step 3: Define Feedback Categories

- **Helpful**: Context was well-selected, good balance
- **Over-provisioned**: Too many files provided, low precision
- **Under-provisioned**: Missing important files, low recall
- **Irrelevant**: Provided files with high relevance scores that weren't useful
- **Missed Dependencies**: Didn't include related/dependent files

### Step 4: Create Feedback Storage (Future Enhancement)

For future implementation:

- Extend `provide_feedback` MCP tool to handle context feedback
- Or create new `record_context_feedback` tool
- Store feedback in `.cortex/context-feedback.json`
- Use data to train/improve relevance scorer

### Step 5: Update Prompts Manifest

Add new prompt to `prompts-manifest.json` with appropriate metadata.

## Technical Design

### Feedback Data Model

```python
class ContextFeedbackRecord:
    session_id: str  # Unique session identifier
    timestamp: str  # ISO format
    task_description: str  # What task was being performed
    
    # What optimize_context provided
    provided_files: list[str]
    provided_sections: dict[str, list[str]]
    relevance_scores: dict[str, float]
    total_tokens_provided: int
    
    # What was actually used (AI analysis)
    files_read: list[str]
    files_modified: list[str]
    files_mentioned: list[str]
    files_needed_but_missing: list[str]
    files_provided_but_unused: list[str]
    
    # Scoring
    precision: float
    recall: float
    f1_score: float
    token_efficiency: float
    
    # Feedback
    feedback_type: str
    suggestions: list[str]
    comment: str | None
```

### Prompt Structure

1. **Recall Phase**: AI recalls optimize_context calls from session
2. **Analysis Phase**: AI analyzes what was actually used
3. **Scoring Phase**: AI calculates metrics
4. **Feedback Phase**: AI provides structured feedback
5. **Storage Phase**: Feedback stored via MCP tool

## Dependencies

- Existing `optimize_context` tool (`src/cortex/tools/phase4_context_operations.py`)
- Existing prompt infrastructure (`.cortex/synapse/prompts/`)
- Cortex MCP tools for file operations (`manage_file`)
- Existing learning engine patterns (`src/cortex/refactoring/learning_engine.py`)

## Success Criteria

- [ ] Analysis prompt created and functional
- [ ] AI can analyze session and provide structured feedback
- [ ] Scoring metrics are well-defined and calculable
- [ ] Feedback format is structured for future automation
- [ ] Prompt added to prompts manifest

## Risks & Mitigation

| Risk | Impact | Mitigation |
|------|--------|------------|
| Session history recall may be imprecise | Medium | Use heuristics, accept approximate analysis |
| Metrics may need refinement | Low | Start simple, iterate based on real usage |
| AI may not accurately identify "used" files | Medium | Provide clear heuristics in prompt |

## Estimated Effort

- **Step 1 (Prompt creation)**: Low (1-2h)
- **Step 2-4 (Metrics & categories)**: Low (included in prompt)
- **Step 5 (Manifest update)**: Low (<1h)
- **Future: MCP tool integration**: Medium (4-8h)

**Total Initial Implementation**: Low (2-4h)

## Future Enhancements

1. **Automated Tracking**: Add usage tracking to MCP tools
2. **Learning Integration**: Feed feedback into relevance scorer training
3. **Dashboard**: Visualize context effectiveness over time
4. **A/B Testing**: Compare different optimization strategies

## Related Plans

- Phase 29: Track MCP Tool Usage for Optimization
- Phase 21: Health-Check and Optimization Analysis System
