# Phase 21: Health-Check and Optimization Analysis System

## Status

**Status**: IN PROGRESS  
**Priority**: Medium  
**Created**: 2026-01-15  
**Target Completion**: 2026-01-30  
**Estimated Effort**: 40-50 hours

**Progress**:

- ✅ Step 1: Create Health-Check Analysis Module - COMPLETE (2026-01-26)
  - Created `src/cortex/health_check/` module with all core components
  - Implemented: PromptAnalyzer, RuleAnalyzer, ToolAnalyzer, SimilarityEngine, DependencyMapper, QualityValidator, ReportGenerator
  - All files within size limits (largest: 292 lines), all functions within length limits
  - Type checking: 0 errors, 0 warnings
  - Tests: 12 tests passing (similarity_engine, quality_validator)
  - Code formatted with Black, all quality gates passing

## Goal

Create a comprehensive health-check system that analyzes prompts, rules, and MCP tools for merge and optimization opportunities without losing quality. Integrate this system into CI/CD pipelines to continuously monitor and suggest improvements.

## Context

### Current State

- **Prompts**: 7 prompts in `.cortex/synapse/prompts/` (commit.md, create-plan.md, implement-next-roadmap-step.md, populate-tiktoken-cache.md, review.md, validate-roadmap-sync.md)
- **Rules**: Multiple rules organized by category (general/, markdown/, python/) in `.cortex/synapse/rules/`
- **MCP Tools**: 53+ tools across 10 phases, organized in multiple modules
- **Existing Health Checks**:
  - `check_structure_health` - project structure validation
  - `validate` - memory bank file validation (schema, duplications, quality, infrastructure, timestamps, roadmap_sync)
  - `check_connection_health` - MCP connection health

### Problem Statement

As the project grows, the size and number of prompts, rules, and MCP tools increases. Without systematic analysis, we risk:

- Duplicate functionality across prompts/rules/tools
- Redundant code and maintenance burden
- Increased cognitive load for developers
- Slower tool discovery and usage
- Token budget inefficiencies

### User Need

Incorporate health-check analysis into pipelines that:

1. Analyzes prompts for merge/optimization opportunities
2. Analyzes rules for merge/optimization opportunities
3. Analyzes MCP tools for merge/optimization opportunities
4. Preserves quality while suggesting optimizations
5. Provides actionable recommendations

## Approach

### High-Level Strategy

1. **Create Analysis Engine**: Build modular analyzers for prompts, rules, and tools
2. **Similarity Detection**: Use content similarity analysis to find merge opportunities
3. **Dependency Analysis**: Map relationships between prompts/rules/tools
4. **Quality Preservation**: Ensure optimizations don't reduce functionality or quality
5. **Pipeline Integration**: Add health-check step to CI/CD workflows
6. **Reporting**: Generate actionable reports with merge/optimization suggestions

### Architecture

```text
Health-Check System
├── Analyzers
│   ├── PromptAnalyzer - Analyzes prompt files for duplicates/merges
│   ├── RuleAnalyzer - Analyzes rule files for duplicates/merges
│   └── ToolAnalyzer - Analyzes MCP tools for consolidation opportunities
├── Similarity Engine
│   ├── Content Similarity - Text similarity analysis
│   ├── Semantic Similarity - Semantic meaning analysis
│   └── Functional Similarity - Functional overlap detection
├── Dependency Mapper
│   ├── Prompt Dependencies - Cross-references between prompts
│   ├── Rule Dependencies - Rule usage patterns
│   └── Tool Dependencies - Tool call patterns and relationships
├── Quality Validator
│   ├── Functionality Preservation - Ensures no feature loss
│   ├── Quality Metrics - Maintains quality scores
│   └── Test Coverage - Verifies test coverage maintained
└── Report Generator
    ├── Merge Suggestions - Actionable merge recommendations
    ├── Optimization Opportunities - Performance/structure improvements
    └── Quality Impact Analysis - Quality preservation verification
```

## Implementation Steps

### Step 1: Create Health-Check Analysis Module

**Location**: `src/cortex/health_check/`

**Files to Create**:

- `__init__.py` - Module initialization
- `prompt_analyzer.py` - Prompt analysis logic
- `rule_analyzer.py` - Rule analysis logic
- `tool_analyzer.py` - MCP tool analysis logic
- `similarity_engine.py` - Similarity detection algorithms
- `dependency_mapper.py` - Dependency relationship mapping
- `quality_validator.py` - Quality preservation validation
- `report_generator.py` - Report generation and formatting

**Key Components**:

1. **PromptAnalyzer**:
   - Scan all prompts in `.cortex/synapse/prompts/`
   - Extract key sections and functionality
   - Detect duplicate or overlapping content
   - Identify merge opportunities
   - Calculate similarity scores

2. **RuleAnalyzer**:
   - Scan all rules in `.cortex/synapse/rules/`
   - Analyze rule categories and organization
   - Detect duplicate rules across categories
   - Identify consolidation opportunities
   - Map rule dependencies

3. **ToolAnalyzer**:
   - Scan all MCP tool implementations
   - Extract tool signatures and functionality
   - Detect overlapping tool capabilities
   - Identify consolidation opportunities
   - Map tool dependencies and usage patterns

**Estimated Effort**: 12-15 hours

### Step 2: Implement Similarity Detection Engine

**Location**: `src/cortex/health_check/similarity_engine.py`

**Features**:

- **Content Similarity**:
  - Token-based similarity (using tiktoken)
  - Text diff analysis
  - Section-by-section comparison
- **Semantic Similarity**:
  - Keyword extraction and matching
  - Topic modeling for semantic overlap
  - Intent analysis for functional similarity
- **Functional Similarity**:
  - Parameter overlap analysis
  - Return type comparison
  - Usage pattern matching

**Algorithms**:

- Jaccard similarity for token sets
- Cosine similarity for vectorized content
- Levenshtein distance for text similarity
- Dependency graph analysis for functional overlap

**Configuration**:

- Similarity thresholds (default: 0.75 for high, 0.60 for medium)
- Minimum content length for analysis (default: 100 tokens)
- Section weighting for importance

**Estimated Effort**: 8-10 hours

### Step 3: Implement Dependency Mapping

**Location**: `src/cortex/health_check/dependency_mapper.py`

**Features**:

- **Prompt Dependencies**:
  - Cross-references between prompts
  - Shared sections and templates
  - Prompt usage patterns
- **Rule Dependencies**:
  - Rule category relationships
  - Rule usage in prompts/tools
  - Rule inheritance patterns
- **Tool Dependencies**:
  - Tool call graphs
  - Shared helper functions
  - Manager dependencies

**Output**:

- Dependency graphs (JSON format)
- Relationship matrices
- Consolidation impact analysis

**Estimated Effort**: 6-8 hours

### Step 4: Implement Quality Preservation Validator

**Location**: `src/cortex/health_check/quality_validator.py`

**Features**:

- **Functionality Preservation**:
  - Feature coverage analysis
  - Parameter compatibility checks
  - Return type validation
- **Quality Metrics**:
  - Code quality scores (maintainability, complexity)
  - Test coverage verification
  - Documentation completeness
- **Impact Analysis**:
  - Breaking change detection
  - Backward compatibility checks
  - Migration path validation

**Validation Rules**:

- No feature loss in merges
- Test coverage maintained or improved
- Documentation updated
- No breaking changes without migration path

**Estimated Effort**: 6-8 hours

### Step 5: Create MCP Tool for Health-Check

**Location**: `src/cortex/tools/health_check_operations.py`

**Tool Signature**:

```python
@mcp.tool()
async def analyze_health_check(
    analysis_type: Literal["prompts", "rules", "tools", "all"],
    similarity_threshold: float = 0.75,
    include_dependencies: bool = True,
    validate_quality: bool = True,
    project_root: str | None = None,
) -> str:
    """Analyze prompts, rules, or tools for merge/optimization opportunities."""
```

**Features**:

- Analyze specific type or all types
- Configurable similarity thresholds
- Dependency analysis option
- Quality validation option
- JSON response with actionable recommendations

**Response Format**:

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
    "optimization_opportunities": [...]
  },
  "rules": {...},
  "tools": {...},
  "recommendations": [...]
}
```

**Estimated Effort**: 8-10 hours

### Step 6: Create CLI Script for Health-Check

**Location**: `scripts/health_check.py`

**Features**:

- Standalone script for manual health-check runs
- JSON output for CI/CD integration
- Configurable analysis options
- Report generation (markdown, JSON, HTML)

**Usage**:

```bash
python scripts/health_check.py --type all --threshold 0.75 --output report.json
```

**Estimated Effort**: 4-5 hours

### Step 7: Integrate into CI/CD Pipeline

**Location**: `.github/workflows/quality.yml`

**Changes**:

- Add health-check step after code quality checks
- Run health-check analysis
- Generate health-check report
- Upload report as artifact
- Optionally fail on critical issues (configurable)

**Workflow Step**:

```yaml
- name: Health-Check Analysis
  run: |
    uv run python scripts/health_check.py \
      --type all \
      --threshold 0.75 \
      --output health-check-report.json \
      --format json
  continue-on-error: true

- name: Upload Health-Check Report
  uses: actions/upload-artifact@v4
  with:
    name: health-check-report
    path: health-check-report.json
```

**Estimated Effort**: 2-3 hours

### Step 8: Create Unit Tests

**Location**: `tests/health_check/`

**Test Files**:

- `test_prompt_analyzer.py` - Prompt analyzer tests
- `test_rule_analyzer.py` - Rule analyzer tests
- `test_tool_analyzer.py` - Tool analyzer tests
- `test_similarity_engine.py` - Similarity engine tests
- `test_dependency_mapper.py` - Dependency mapper tests
- `test_quality_validator.py` - Quality validator tests
- `test_health_check_operations.py` - MCP tool tests

**Coverage Target**: 90%+ coverage for all health-check modules

**Estimated Effort**: 8-10 hours

### Step 9: Documentation

**Files to Create/Update**:

- `docs/guides/health-check.md` - User guide for health-check system
- `docs/api/health-check.md` - API reference for health-check tools
- Update `docs/api/tools.md` - Add health-check tool documentation

**Content**:

- How to run health-check analysis
- Understanding health-check reports
- Interpreting merge/optimization suggestions
- Quality preservation guarantees
- CI/CD integration guide

**Estimated Effort**: 3-4 hours

## Technical Design

### Similarity Detection Algorithm

**For Prompts/Rules**:

1. Tokenize content using tiktoken
2. Extract key sections (headings, code blocks, lists)
3. Calculate section-level similarity
4. Weight sections by importance (headings > code > text)
5. Aggregate similarity scores
6. Apply threshold filtering

**For Tools**:

1. Extract function signatures (parameters, return types)
2. Analyze docstrings for functionality description
3. Compare implementation patterns
4. Map shared dependencies
5. Calculate functional overlap score

### Merge Suggestion Criteria

**High Confidence Merge** (similarity > 0.85):

- Strong recommendation to merge
- Clear quality improvement expected
- Minimal risk of functionality loss

**Medium Confidence Merge** (similarity 0.70-0.85):

- Consider merging after review
- Quality impact needs validation
- Requires manual verification

**Low Confidence Merge** (similarity 0.60-0.70):

- Potential optimization opportunity
- Requires careful analysis
- May benefit from refactoring instead

### Quality Preservation Rules

1. **No Feature Loss**: All features from merged items must be preserved
2. **Test Coverage**: Test coverage must be maintained or improved
3. **Documentation**: Documentation must be updated and complete
4. **Backward Compatibility**: Breaking changes require migration path
5. **Performance**: Merged items should not degrade performance

## Dependencies

### Internal Dependencies

- `cortex.core.token_counter` - Token counting for similarity analysis
- `cortex.core.path_resolver` - Path resolution for file scanning
- `cortex.tools.validate` - Quality validation integration
- `cortex.analysis.pattern_analyzer` - Pattern analysis for tool similarity

### External Dependencies

- `tiktoken` - Token counting (already in requirements)
- `difflib` - Text diff analysis (stdlib)
- No new external dependencies required

## Success Criteria

1. ✅ Health-check system analyzes prompts, rules, and tools
2. ✅ Similarity detection identifies merge opportunities with >75% accuracy
3. ✅ Quality preservation validator ensures no functionality loss
4. ✅ MCP tool provides actionable recommendations
5. ✅ CI/CD integration runs health-check automatically
6. ✅ Unit tests achieve 90%+ coverage
7. ✅ Documentation complete and comprehensive
8. ✅ Health-check reports are actionable and clear

## Risks & Mitigation

### Risk 1: False Positives in Merge Suggestions

**Mitigation**:

- Use multiple similarity algorithms
- Require manual review for medium/low confidence merges
- Validate quality impact before suggesting merges

### Risk 2: Quality Degradation from Merges

**Mitigation**:

- Comprehensive quality validation
- Test coverage verification
- Manual review process for high-impact changes

### Risk 3: Performance Impact of Analysis

**Mitigation**:

- Cache similarity results
- Incremental analysis (only changed files)
- Run analysis asynchronously in CI/CD

### Risk 4: Breaking Changes from Tool Consolidation

**Mitigation**:

- Backward compatibility checks
- Migration path validation
- Deprecation period for consolidated tools

## Timeline

- **Week 1** (Days 1-5): Steps 1-3 (Analysis modules, similarity engine, dependency mapper)
- **Week 2** (Days 6-10): Steps 4-6 (Quality validator, MCP tool, CLI script)
- **Week 3** (Days 11-15): Steps 7-9 (CI/CD integration, tests, documentation)

**Total**: 15 working days (40-50 hours)

## Testing Strategy

### Unit Tests

- Test each analyzer independently
- Test similarity algorithms with known inputs
- Test quality validation with various scenarios
- Test report generation with different configurations

### Integration Tests

- Test full health-check workflow
- Test MCP tool integration
- Test CI/CD pipeline integration
- Test with real prompts/rules/tools

### Validation Tests

- Verify similarity detection accuracy
- Verify quality preservation
- Verify no false positives in merge suggestions
- Verify report accuracy and completeness

## Notes

- Health-check should be non-destructive (read-only analysis)
- Merge suggestions are recommendations, not automatic changes
- Quality preservation is critical - never suggest merges that reduce quality
- CI/CD integration should be non-blocking (continue-on-error: true)
- Reports should be actionable with clear next steps

## Related Plans

- [Phase 9: Excellence 9.8+](../phase-9-excellence-98.md) - Quality improvements
- [Phase 12: Convert Commit Workflow Prompts to MCP Tools](../archive/Phase12/phase-12-commit-workflow-mcp-tools.md) - Tool consolidation precedent
- [Refactor Setup Prompts: Simplify to 3 Prompts](../refactor-setup-prompts.md) - Prompt consolidation example
