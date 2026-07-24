# Health-Check Analysis Guide

The health-check system analyzes Cortex prompts, rules, and MCP tools for merge and optimization opportunities without losing quality. Use it to reduce duplication, improve maintainability, and keep token usage efficient.

## Overview

- **Prompts**: Scans `.cortex/synapse/prompts/` for overlapping or duplicate content.
- **Rules**: Analyzes rules by category for consolidation opportunities.
- **Tools**: Scans MCP tool implementations for functional overlap and consolidation.

The system is **read-only**: it suggests changes but does not modify files.

## Running Health-Check

### CLI (cortex.health_check)

The health-check CLI lives in `src/cortex/health_check/__main__.py`. Run from the project root:

```bash
# Analyze all (prompts, rules, tools) with default threshold 0.75
uv run python -m cortex.health_check --type all --output report.json

# Prompts only, higher threshold, Markdown report
uv run python -m cortex.health_check --type prompts --threshold 0.8 --format markdown

# JSON to stdout
uv run python -m cortex.health_check --type rules --format json
```

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `--type` | `prompts`, `rules`, `tools`, or `all` | `all` |
| `--threshold` | Similarity threshold 0.0–1.0 | `0.75` |
| `--output` | Output file path | stdout |
| `--format` | `json` or `markdown` | `json` |
| `--project-root` | Project root directory | current dir |
| `--no-dependencies` | Skip dependency mapping | off |
| `--no-quality-validation` | Skip quality validation | off |

### MCP Tool (analyze_health_check)

From an MCP client (e.g. Claude Code), call the `analyze_health_check` tool with:

- `analysis_type`: `"prompts"`, `"rules"`, `"tools"`, or `"all"`
- `similarity_threshold`: float (default `0.75`)
- `include_dependencies`: bool (default `true`)
- `validate_quality`: bool (default `true`)
- `project_root`: optional path

The tool returns a JSON string with `status`, `analysis_type`, `prompts`, `rules`, `tools`, `recommendations`, and optionally `prompt_dependencies` and `rule_dependencies`.

## Understanding Reports

### Merge opportunities

- **High confidence** (e.g. similarity ≥ 0.85): Strong candidate to merge; low risk.
- **Medium** (e.g. 0.70–0.85): Consider merging after review; validate impact.
- **Low** (e.g. 0.60–0.70): Possible optimization; may be better as refactors.

### Quality impact

- **positive**: Merge expected to improve clarity or reduce duplication.
- **neutral**: No clear quality change.
- **negative**: Merge could reduce quality; treat as “review” or “do not merge”.

### Recommendations

The `recommendations` list includes quality-validator issues (e.g. low similarity, negative impact). Address these before merging.

## CI/CD Integration

The Code Quality workflow (`.github/workflows/quality.yml`) runs health-check after tests with `continue-on-error: true`. The job does not fail if health-check fails. The report is uploaded as the `health-check-report` artifact when the step succeeds.

To run locally in a CI-like way:

```bash
uv run python -m cortex.health_check --type all --threshold 0.75 --output health-check-report.json --format json
```

## Quality Preservation

The quality validator ensures:

- **No feature loss**: Merges must preserve behavior.
- **Similarity threshold**: Pairs below the threshold are flagged.
- **Impact check**: Negative quality impact is reported.

Merge suggestions are recommendations only; apply them after review and tests.

## See Also

- [API Reference: Health-Check](../api/health-check.md) – Tool and types reference.
- [API Reference: Tools](../api/tools.md) – Full MCP tools list including `analyze_health_check`.
