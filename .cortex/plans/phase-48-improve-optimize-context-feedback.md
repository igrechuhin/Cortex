# Phase 48: Improve optimize_context with Session Feedback Analysis

## Status

**PLANNING** (2026-01-19)

## Goal

Create an end-of-session prompt that analyzes `optimize_context` effectiveness and provides structured feedback to improve future context optimization based on real-world usage patterns.

## Context

### Problem Statement

The `optimize_context` MCP tool selects files and sections to include in context based on relevance scoring, but there's no feedback loop to validate whether the selected context was actually useful. This means:

1. No data on whether selected files were actually used
2. No way to identify files that were needed but not provided
3. No metrics to measure context optimization effectiveness
4. No mechanism to improve relevance scoring over time

### Current State

- `optimize_context` returns: `selected_files`, `selected_sections`, `total_tokens`, `utilization`, `excluded_files`, `relevance_scores`
- No tracking of what context was actually used during a session
- No feedback mechanism for context optimization
- Relevance scoring is static, not learning from usage

### User Need

Users want to improve `optimize_context` effectiveness by:

1. Analyzing what context was provided vs. what was actually used
2. Creating scoring metrics to measure effectiveness
3. Building a feedback loop to improve future context selection

## Approach

### Phase 1: Analysis Prompt (This Plan)

Create an end-of-session prompt that guides the AI to:

1. Recall `optimize_context` calls made during the session
2. Analyze what context was actually used (files read, modified, mentioned)
3. Calculate effectiveness metrics (precision, recall, F1, token efficiency)
4. Provide structured feedback for improvement

### Phase 2: Feedback Storage (Future)

- Create MCP tool to store context feedback
- Build feedback database in `.cortex/context-feedback.json`
- Integrate with existing learning infrastructure

### Phase 3: Learning Integration (Future)

- Use feedback data to improve relevance scoring
- Adjust weights based on historical usage patterns
- Implement adaptive context optimization

## Implementation Steps

### Step 1: Create Analysis Prompt

**File**: `.cortex/synapse/prompts/analyze-context-effectiveness.md`

**Content Structure**:

1. **Pre-Analysis Checklist**: Instructions to recall optimize_context calls
2. **Usage Analysis**: Guide to identify what was actually used
3. **Scoring Metrics**: Definitions and calculation methods
4. **Feedback Categories**: Classification of optimization effectiveness
5. **Output Format**: Structured feedback specification

**Scoring Metrics**:

- **Precision**: `files_used / files_provided` (higher = less waste)
- **Recall**: `files_used / files_needed` (higher = better coverage)
- **F1 Score**: `2 * (precision * recall) / (precision + recall)`
- **Token Efficiency**: `useful_tokens / total_tokens_provided`
- **Relevance Accuracy**: Correlation between relevance scores and actual usage

**Feedback Categories**:

- `helpful`: Context was well-selected
- `over_provisioned`: Too many files provided
- `under_provisioned`: Missing important files
- `irrelevant`: Provided files that weren't useful
- `missed_dependencies`: Didn't include related files

### Step 2: Define Feedback Schema

**Data Model** (for future MCP tool):

```python
class ContextFeedbackRecord(BaseModel):
    """Record of context optimization feedback."""
    
    session_id: str  # Unique session identifier
    timestamp: str  # ISO format (YYYY-MM-DDTHH:MM)
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
    feedback_type: str  # helpful, over_provisioned, under_provisioned, etc.
    suggestions: list[str]
    comment: str | None = None
```

### Step 3: Update Prompts Manifest

Add entry to `.cortex/synapse/prompts/prompts-manifest.json`:

```json
{
  "name": "analyze-context-effectiveness",
  "description": "Analyze optimize_context effectiveness at end of session",
  "file": "analyze-context-effectiveness.md",
  "category": "analysis",
  "usage": "Run at end of chat session to provide feedback on context optimization"
}
```

### Step 4: Testing and Validation

1. Test prompt with various session scenarios
2. Validate scoring metrics are meaningful
3. Ensure feedback format is actionable
4. Iterate based on real usage

## Technical Design

### Prompt Flow

```text
1. RECALL PHASE
   └── AI recalls optimize_context calls from session
       ├── Task descriptions used
       ├── Files/sections selected
       └── Relevance scores assigned

2. ANALYSIS PHASE
   └── AI analyzes actual usage
       ├── Files that were read (Read tool calls)
       ├── Files that were modified (Write/Edit calls)
       ├── Files mentioned in conversation
       └── Files that were needed but not provided

3. SCORING PHASE
   └── AI calculates metrics
       ├── Precision = used / provided
       ├── Recall = used / (used + needed_but_missing)
       ├── F1 = harmonic mean
       └── Token efficiency estimate

4. FEEDBACK PHASE
   └── AI provides structured feedback
       ├── Feedback category classification
       ├── Specific improvement suggestions
       └── Actionable recommendations

5. OUTPUT PHASE
   └── Structured output
       ├── JSON feedback record
       ├── Human-readable summary
       └── Storage instructions
```

### Integration Points

1. **Prompt Execution**: Standard Cursor command execution
2. **Feedback Storage**: Initially manual (copy to file), later via MCP tool
3. **Learning Integration**: Future phase - feed into relevance scorer

### Challenges and Mitigations

| Challenge | Mitigation |
|-----------|------------|
| Session history recall imprecise | Use heuristics, ask AI to be conservative |
| Objective measurement difficult | Define clear criteria, iterate based on feedback |
| Multiple optimize_context calls | Analyze each separately, provide aggregate |
| No direct session access | Rely on AI's conversation context |

## Dependencies

- Existing `optimize_context` tool (Phase 4)
- Existing prompt infrastructure (`.cortex/synapse/prompts/`)
- Cortex MCP tools for file operations

## Success Criteria

- [ ] Prompt created at `.cortex/synapse/prompts/analyze-context-effectiveness.md`
- [ ] Prompt provides clear instructions for session analysis
- [ ] Scoring metrics are well-defined and calculable
- [ ] Feedback format is structured and actionable
- [ ] Prompts manifest updated
- [ ] Documentation complete

## Risks and Mitigation

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| Imprecise session recall | Medium | High | Use conservative estimates, iterate |
| Metrics not meaningful | Medium | Medium | Start simple, refine based on usage |
| Low adoption | Low | Medium | Make prompt easy to use, show value |

## Estimated Effort

- **Step 1 (Prompt)**: Low (1-2h)
- **Step 2 (Schema)**: Low (1h) - documentation only for now
- **Step 3 (Manifest)**: Low (<1h)
- **Step 4 (Testing)**: Medium (2-4h)
- **Total**: Low-Medium (4-8h)

## Future Enhancements

1. **MCP Tool for Feedback**: Create `record_context_feedback` tool
2. **Automated Tracking**: Track file usage automatically during session
3. **Learning Integration**: Use feedback to improve relevance scoring
4. **Analytics Dashboard**: Visualize context optimization effectiveness over time
5. **A/B Testing**: Compare different optimization strategies

## Related Plans

- Phase 4: Context Optimization (original implementation)
- Phase 29: Track MCP Tool Usage for Optimization
- Phase 21: Health-Check and Optimization Analysis System

## Notes

- This is an incremental improvement that can be built upon
- Start with manual analysis, automate later
- Focus on collecting actionable feedback first
- Metrics may need refinement based on real usage patterns
