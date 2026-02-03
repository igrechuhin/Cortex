# Health-Check API Reference

Reference for the health-check analysis system: MCP tool, CLI, and report shape.

## MCP Tool: analyze_health_check

Analyze prompts, rules, and/or MCP tools for merge and optimization opportunities.

**USE WHEN:** You need a health-check of prompts, rules, or tools; merge/optimization suggestions; or dependency mapping.

**Examples:** “Analyze health check for all”, “Analyze prompts only with threshold 0.8”, “Run health check with dependencies”.

### Parameters

| Parameter | Type | Default | Description |
|----------|------|---------|-------------|
| `analysis_type` | `"prompts"` \| `"rules"` \| `"tools"` \| `"all"` | `"all"` | What to analyze |
| `similarity_threshold` | float | `0.75` | Minimum similarity for merge candidates (0.0–1.0) |
| `include_dependencies` | bool | `true` | Include prompt/rule dependency maps |
| `validate_quality` | bool | `true` | Run quality validation on merge opportunities |
| `project_root` | str \| None | None | Project root (default: current directory) |

### Returns

JSON string with:

- `status`: `"success"`
- `analysis_type`: as requested
- `prompts`: `PromptAnalysisResult`
- `rules`: `RuleAnalysisResult`
- `tools`: `ToolAnalysisResult`
- `recommendations`: list of strings (quality issues / suggestions)
- `prompt_dependencies`: (optional) map prompt name → list of referenced prompt names
- `rule_dependencies`: (optional) map rule path → list of referenced rule paths

### Example response (structure)

```json
{
  "status": "success",
  "analysis_type": "all",
  "prompts": {
    "total": 7,
    "merge_opportunities": [
      {
        "files": ["prompt1.md", "prompt2.md"],
        "similarity": 0.85,
        "merge_suggestion": "Merge into unified prompt",
        "quality_impact": "positive",
        "estimated_savings": "15% tokens"
      }
    ],
    "optimization_opportunities": []
  },
  "rules": { "total": 20, "categories": [], "merge_opportunities": [], "optimization_opportunities": [] },
  "tools": { "total": 53, "merge_opportunities": [], "optimization_opportunities": [], "consolidation_opportunities": [] },
  "recommendations": [],
  "prompt_dependencies": {},
  "rule_dependencies": {}
}
```

## CLI: python -m cortex.health_check

Package entry point for manual or CI runs (implementation: `src/cortex/health_check/__main__.py`).

**Usage:**

```bash
uv run python -m cortex.health_check --type all --threshold 0.75 --output report.json --format json
```

**Arguments:** See [Health-Check Guide](../guides/health-check.md#cli-cortexhealth_check).

## Report types

- **PromptAnalysisResult**: `total`, `merge_opportunities`, `optimization_opportunities`
- **RuleAnalysisResult**: `total`, `categories`, `merge_opportunities`, `optimization_opportunities`
- **ToolAnalysisResult**: `total`, `merge_opportunities`, `optimization_opportunities`, `consolidation_opportunities`
- **MergeOpportunity**: `files`, `similarity`, `merge_suggestion`, `quality_impact`, `estimated_savings`

## See Also

- [Health-Check Guide](../guides/health-check.md) – How to run and interpret reports
- [Tools API](tools.md) – Full MCP tools list
