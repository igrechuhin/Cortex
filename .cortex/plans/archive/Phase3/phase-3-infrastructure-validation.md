# Phase 3 Extension: Infrastructure Validation

**Status:** ✅ COMPLETE (2026-01-12)  
**Priority:** High  
**Dependencies:** Phase 3 ✅ Complete  
**Estimated Effort:** 2-3 hours implementation + 1 hour testing

---

## Problem Statement

The current Phase 3 validation tools (`validate` and `configure`) only validate **Memory Bank content**:

- Schema validation (Memory Bank file structure)
- Duplication detection (Memory Bank content)
- Quality metrics (Memory Bank quality scores)

**Missing:** Project infrastructure consistency validation that would catch:

- Commit prompt not matching CI workflow requirements
- Code quality checks missing from commit procedure
- Rules/prompts/workflows out of sync
- Documentation inconsistencies

**Impact:** Issues like commit prompt missing code quality checks are only caught by CI failures, not proactively.

---

## Proposed Solution

Extend the `validate` tool with a new check type: `"infrastructure"` or `"consistency"` that validates:

### 1. Commit Procedure vs CI Workflow Alignment

**Check:** Ensure `.cortex/synapse/prompts/commit.md` includes all checks from `.github/workflows/quality.yml`

**Validation Logic:**

- Parse CI workflow to extract check steps
- Parse commit prompt to extract procedure steps
- Compare and report missing checks
- Suggest additions to commit prompt

**Example Issues Detected:**

- Missing file size check in commit prompt
- Missing function length check in commit prompt
- Missing code quality validation step
- Out-of-order steps

### 2. Code Quality Standards Consistency

**Check:** Ensure code quality standards are consistently enforced:

- Rules files match actual enforcement
- Scripts exist for all checks mentioned in rules
- CI workflow includes all required checks

### 3. Documentation Consistency

**Check:** Ensure documentation matches implementation:

- API docs match tool signatures
- Examples in docs match actual behavior
- README matches current features

### 4. Configuration Consistency

**Check:** Ensure configuration files are consistent:

- Validation config matches validation implementation
- Optimization config matches optimization strategies
- Rules config matches rules manager behavior

---

## Implementation Plan

### Step 1: Add Infrastructure Validation Module

**File:** `src/cortex/validation/infrastructure_validator.py`

**Features:**

- Parse CI workflow YAML
- Parse commit prompt markdown
- Compare check steps
- Generate alignment report

### Step 2: Extend `validate` Tool

**Update:** `src/cortex/tools/validation_operations.py`

**New Check Type:**

```python
check_type: Literal["schema", "duplications", "quality", "infrastructure"]
```

**New Function:**

```python
async def validate_infrastructure(
    project_root: str | None = None,
    check_commit_ci_alignment: bool = True,
    check_code_quality_consistency: bool = True,
    check_documentation_consistency: bool = True,
    check_config_consistency: bool = True,
) -> str:
    """Validate project infrastructure consistency."""
```

### Step 3: Add Validation Logic

**CI vs Commit Prompt Alignment:**

- Extract steps from `.github/workflows/quality.yml`
- Extract steps from `.cortex/synapse/prompts/commit.md`
- Compare and report mismatches
- Suggest fixes

**Code Quality Consistency:**

- Check that all rules have corresponding enforcement
- Verify scripts exist for all checks
- Ensure CI includes all required checks

---

## Expected Output

```json
{
  "status": "success",
  "check_type": "infrastructure",
  "checks_performed": {
    "commit_ci_alignment": true,
    "code_quality_consistency": true,
    "documentation_consistency": true,
    "config_consistency": true
  },
  "issues_found": [
    {
      "type": "missing_check",
      "severity": "high",
      "description": "Commit prompt missing file size check",
      "location": ".cortex/synapse/prompts/commit.md",
      "suggestion": "Add file size check step after formatting step",
      "ci_check": "Check file sizes (max 400 lines)",
      "missing_in_commit": true
    }
  ],
  "recommendations": [
    "Add code quality checks step to commit prompt",
    "Synchronize commit prompt with CI workflow"
  ]
}
```

---

## Benefits

1. **Proactive Detection:** Catch infrastructure inconsistencies before CI failures
2. **Automated Validation:** Regular validation ensures consistency
3. **Actionable Reports:** Clear suggestions for fixing issues
4. **Prevention:** Prevent future drift between commit prompt and CI

---

## Integration with Existing Validation

This extends Phase 3 validation to cover:

- ✅ Memory Bank content (existing)
- ✅ Project infrastructure (new)

Both can be run together:

```bash
# Validate Memory Bank quality
validate(check_type="quality")

# Validate infrastructure consistency
validate(check_type="infrastructure")
```

---

## Timeline

- **Implementation:** 2-3 hours
  - Infrastructure validator module: 1 hour
  - Extend validate tool: 0.5 hours
  - CI vs Commit prompt comparison: 0.5-1 hour
  - Testing: 0.5 hours

- **Testing:** 1 hour
  - Unit tests for validator
  - Integration tests
  - Edge case testing

**Total:** 3-4 hours

---

## Success Criteria

- ✅ Infrastructure validation detects commit prompt vs CI misalignment
- ✅ Validation reports actionable suggestions
- ✅ All infrastructure checks pass for current project state
- ✅ Validation can be run regularly to prevent drift
