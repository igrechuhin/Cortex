# Phase 51: Enhance Context Analysis with Actionable Insights

**Status:** COMPLETE
**Priority:** High
**Created:** 2026-01-21
**Completed:** 2026-01-21

## Goal

Enhance the context analysis system to store actionable insights alongside raw statistics, enabling future optimization of `load_context` behavior based on learned patterns.

## Problem

Current statistics storage captures only raw metrics:

- Token utilization percentages
- File counts
- Relevance scores

Missing actionable insights:

- Which files are consistently useful for specific task types
- Recommended token budgets per task type
- Learned patterns about file effectiveness
- Recommendations for future `load_context` calls

## Solution

Enhance `ContextUsageStatistics` to include:

1. **Task-type recommendations** - Per-task-type insights (budget, essential files)
2. **File effectiveness tracking** - Per-file stats (times selected, avg relevance, usefulness)
3. **Learned patterns** - Human-readable insights derived from data
4. **Budget recommendations** - Optimal token budgets based on historical utilization

## Implementation

### Step 1: Enhance TypedDicts

Add new types for insights storage:

```python
class TaskTypeInsight(TypedDict):
    calls_count: int
    recommended_budget: int
    essential_files: list[str]
    avg_utilization: float
    avg_relevance: float
    notes: str

class FileEffectiveness(TypedDict):
    times_selected: int
    avg_relevance: float
    task_types_used: list[str]
    recommendation: str

class ContextInsights(TypedDict):
    task_type_recommendations: dict[str, TaskTypeInsight]
    file_effectiveness: dict[str, FileEffectiveness]
    learned_patterns: list[str]
    budget_recommendations: dict[str, int]
```

### Step 2: Update Statistics Structure

Extend `ContextUsageStatistics` to include insights.

### Step 3: Implement Insight Generation

Add functions to:

- Generate task-type insights from entry history
- Calculate file effectiveness scores
- Derive learned patterns from data
- Compute optimal budget recommendations

### Step 4: Update Analysis Functions

Modify `analyze_current_session` and `analyze_session_logs` to generate insights.

## Success Criteria

- Statistics file includes actionable insights
- Insights are updated after each analysis
- Task-type recommendations provide useful guidance
- File effectiveness helps optimize file selection
- Learned patterns are human-readable and actionable
