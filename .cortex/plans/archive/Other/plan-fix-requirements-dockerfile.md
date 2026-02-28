# Fix requirements.txt and Dockerfile Dependency Gap

**Status**: COMPLETE
**Priority**: CRITICAL
**Created**: 2026-02-28
**Type**: Fix
**Effort**: Small (15 min)

## Goal

Fix `requirements.txt` to include all core dependencies from `pyproject.toml`, ensuring Docker builds produce a functional server.

## Context

`requirements.txt` is missing 4 core dependencies that are declared in `pyproject.toml`:

- `pydantic>=2.0.0` (core data modeling)
- `watchdog>=4.0.0` (file watching)
- `tiktoken>=0.5.0` (token counting)
- `pyyaml>=6.0.0` (YAML parsing)

The `Dockerfile` runs `pip install -r requirements.txt`, so Docker builds are missing critical dependencies and the server would fail at runtime with `ModuleNotFoundError`.

## Approach

Migrate Dockerfile to install from `pyproject.toml` directly (source of truth) instead of maintaining a separate `requirements.txt`. This eliminates the sync problem permanently.

## Implementation Steps

1. **Audit current state**: Compare `requirements.txt` against `pyproject.toml [project.dependencies]` to confirm the 4 missing deps
2. **Update Dockerfile**: Change `pip install -r requirements.txt` to `pip install .` (installs from pyproject.toml)
3. **Update requirements.txt**: Add the 4 missing deps and a header comment: `# Keep in sync with pyproject.toml [project.dependencies]`
4. **Test Docker build**: `docker build -t cortex:test .`
5. **Test runtime**: `docker run cortex:test python -c "import pydantic; import watchdog; import tiktoken; import yaml; print('OK')"`

## Dependencies

None.

## Success Criteria

- Docker build completes without errors
- All imports succeed at runtime in Docker container
- `requirements.txt` lists all dependencies from `pyproject.toml`

## Testing Strategy

- **Coverage Target**: N/A (config-only change)
- **Verification**: Docker build + runtime import test
- **Regression**: Existing CI pipeline (if any) should still pass

## Risks & Mitigation

- **Risk**: `pip install .` may pull dev dependencies → **Mitigation**: Verify only runtime deps are installed
- **Risk**: Alpine packages missing for some deps → **Mitigation**: Test build on Alpine base image

## Timeline

Single session (15 min).

## Notes

The better long-term fix is `pip install .` in Dockerfile since `pyproject.toml` is the single source of truth.
