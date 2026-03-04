# Phase 70: Replace exec() with Safe Templating and Add Path Validation

## Status

PENDING

## Goal

Eliminate the `exec()` security vulnerability in prompt file loading and add path traversal protection to prevent arbitrary file reads.

## Context

The code review (2026-03-04) identified two related security issues:

- **CRITICAL**: `exec()` with file-derived input in `src/cortex/tools/synapse/prompts.py` allows arbitrary code execution if prompt files are tampered with
- **MEDIUM**: Prompt file loading lacks path traversal protection, allowing reads outside the expected prompts directory

These are the highest-priority security findings from the review.

## Approach

Replace `exec()` with a safe template rendering approach (Jinja2 sandboxed environment or `string.Template`), and add path resolution validation to restrict file loading to the prompts directory.

## Implementation Steps

### Step 1: Audit ALL exec() usage across full codebase

- **Search the entire repository** for `exec(` — not just `src/cortex/tools/synapse/prompts.py`
- Known location: `src/cortex/tools/synapse/prompts.py:148` — `exec(func_code, globals())`
- Catalog all template variables and dynamic behavior the exec currently supports
- Identify the minimal rendering capability needed
- **IMPORTANT**: A previous agent audit only searched `cortex/` and missed checking other directories. The search MUST cover the full repo tree

### Step 2: Replace exec() with safe templating

- Replace `exec()` with `string.Template` or Jinja2 `SandboxedEnvironment`
- Ensure all existing prompt rendering functionality is preserved
- Remove any dynamic code execution paths

### Step 3: Add path validation for prompt file loading

- Add `Path.resolve()` check to verify loaded files stay within the prompts base directory
- Reject paths containing `..` after resolution
- Return clear error messages for invalid paths

### Step 4: Post-implementation verification (MANDATORY)

- **Re-read the modified source file** after editing to confirm the change was applied correctly
- **Re-run the full-codebase `exec(` search** to confirm zero remaining instances
- This step exists because a prior agent claimed to have removed exec() but changes were never committed

### Step 5: Add tests

- Test normal prompt rendering with safe templating
- Test path traversal prevention (reject `../../../etc/passwd` style paths)
- Test malicious template content handling
- Test all existing prompt rendering still works

## Dependencies

None.

## Success Criteria

- Zero `exec()` calls in production code
- Prompt rendering uses safe templating (no dynamic code execution)
- Path traversal attempts are rejected with clear error
- All existing prompt functionality preserved
- 95%+ test coverage for changed code

## Testing Strategy

- **Unit Tests**: Test template rendering with various prompt files, test path validation with valid/invalid paths
- **Edge Cases**: Malicious template content, path traversal attempts (`..`, symlinks), empty prompts, missing template variables
- **Regression**: All existing prompt tests still pass
- **Coverage Target**: 95%+ for modified modules

## Risks & Mitigation

- **Risk**: Some prompts may rely on exec() dynamic behavior that templates cannot replicate
- **Mitigation**: Audit all prompt files before migration; if complex logic is needed, extract to explicit Python functions called by name rather than exec'd
- **Risk**: Implementation appears successful but changes are not committed/persisted
- **Mitigation**: Step 4 mandates post-implementation verification — re-read source and re-search codebase

## Timeline

Low-Medium effort (4-8h)
