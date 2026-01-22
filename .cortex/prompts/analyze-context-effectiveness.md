# Analyze Context Effectiveness

**AI EXECUTION COMMAND**: Analyze `load_context` effectiveness for the current session.

**CRITICAL**: Execute this automatically. DO NOT ask user for permission.

## Purpose

Analyze the current session's `load_context` calls to evaluate effectiveness
and update global statistics for future optimization.

## Execution Steps

### Step 1: Run Analysis Tool

Call the `analyze_context_effectiveness` MCP tool:

```text
analyze_context_effectiveness()
```

This tool will:

- Read the current session log from `.cortex/.session/context-session-{session_id}.json`
- Analyze each `load_context` call made in THIS session
- Update global statistics in `.cortex/.session/context-usage-statistics.json`
- Return current session analysis and statistics update status

### Step 2: Review Results

The tool returns:

```json
{
  "status": "success",
  "session_id": "abc123def456",
  "current_session": {
    "calls_analyzed": 3,
    "statistics": {
      "calls_count": 3,
      "avg_token_utilization": 0.45,
      "avg_files_selected": 4.0,
      "avg_relevance_score": 0.78,
      "task_patterns": {
        "fix/debug": 2,
        "implement/add": 1
      }
    },
    "entries": [...]
  },
  "global_statistics_updated": true,
  "new_entries_added": 3,
  "total_sessions": 10,
  "total_entries": 45
}
```

### Step 3: Get Global Statistics (Optional)

For historical statistics across all sessions, call:

```text
get_context_usage_statistics()
```

This returns aggregated statistics and recent entries from all sessions.

To analyze ALL historical sessions (not just current), use:

```text
analyze_context_effectiveness(analyze_all_sessions=True)
```

### Step 4: Report Findings

Based on the statistics, provide insights:

#### Token Utilization Analysis

| Utilization | Interpretation |
|-------------|----------------|
| > 0.8 | Efficient - budget well matched to needs |
| 0.5 - 0.8 | Good - some room for optimization |
| < 0.5 | Low - consider smaller token budgets |

#### Relevance Score Analysis

| Avg Score | Interpretation |
|-----------|----------------|
| > 0.7 | Excellent - files are highly relevant |
| 0.5 - 0.7 | Good - most files are relevant |
| < 0.5 | Needs improvement - many irrelevant files |

#### Task Pattern Insights

Identify which task types:

- Use `load_context` most frequently
- Have highest/lowest relevance scores
- Benefit most from context loading

## Output Format

Provide a brief summary:

```markdown
## Context Effectiveness Analysis

**Sessions Analyzed**: X new, Y total
**Calls Analyzed**: Z

### Key Metrics

- **Avg Token Utilization**: X% [Good/Needs Improvement]
- **Avg Files Selected**: X files
- **Avg Relevance Score**: X [Excellent/Good/Needs Improvement]

### Task Patterns

Most common: [pattern] (X calls)

### Recommendations

1. [Specific recommendation based on data]
2. [Specific recommendation based on data]
```

## When No Data

If the tool returns `"status": "no_data"`:

```markdown
## Context Effectiveness Analysis

**No session logs found.**

To generate data:
1. Use `load_context()` at the start of tasks
2. Complete several sessions
3. Run this analysis again
```

## Data Files

- **Session logs**: `.cortex/.session/context-session-{session_id}.json`
- **Statistics**: `.cortex/.session/context-usage-statistics.json`

Each session log contains:

```json
{
  "session_id": "abc123def456",
  "session_start": "2026-01-21T10:30",
  "load_context_calls": [
    {
      "timestamp": "2026-01-21T10:35",
      "task_description": "Fix security vulnerabilities",
      "token_budget": 50000,
      "strategy": "dependency_aware",
      "selected_files": ["activeContext.md", "roadmap.md"],
      "selected_sections": {},
      "total_tokens": 3500,
      "utilization": 0.07,
      "excluded_files": ["techContext.md"],
      "relevance_scores": {
        "activeContext.md": 0.85,
        "roadmap.md": 0.72
      }
    }
  ]
}
```

## Future Optimization

Statistics collected here will be used to:

1. **Tune relevance scoring** - Improve file selection accuracy
2. **Optimize token budgets** - Suggest appropriate budgets per task type
3. **Identify patterns** - Learn which files are needed for which tasks
4. **Reduce waste** - Minimize unused context tokens
