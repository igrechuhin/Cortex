# Comprehensive Project Review (2026-03-07)

## Scope and method

This review covered repository structure, build/test tooling, key validation modules, and documentation consistency.

### Data points gathered

- Source files: 576 Python files under `src/`
- Test files: 279 `test_*.py` files under `tests/`
- Largest modules are ~500–617 lines each (multiple modules exceed 550 lines)

## Executive summary

The project has strong breadth (tests, docs, architecture notes), but there are several consistency and maintainability gaps that can create avoidable risk:

1. **Tooling/docs drift** (type-checkers, coverage guidance, tool counts).
2. **Validation model duplication** in roadmap sync domain.
3. **Potential false negatives** in TODO scanning due to broad exclusion regex.
4. **Potential sensitive-data leakage** via verbose roadmap content logging.
5. **Large-module concentration** that increases change risk and review cost.

## Priority findings

| ID | Severity | Area | Finding | Why it matters |
|---|---|---|---|---|
| F1 | High | Documentation accuracy | `docs/guides/troubleshooting.md` contains contradictory guidance: it correctly says coverage is not in `pytest.ini` addopts, but later says `pytest.ini` sets `--cov-fail-under=90`. | Confuses contributors and leads to wrong debugging actions. |
| F2 | High | Validation correctness | TODO scanner excludes any file path containing `test`, `example`, `sample`, or `demo` anywhere in the path string. | Can silently skip production files (false negatives), weakening roadmap-sync guarantees. |
| F3 | Medium | Architecture/maintainability | Roadmap sync models are defined twice (`roadmap_models.py` and `roadmap_sync.py`) with overlapping semantics and diverging fields. | Increases API confusion and drift risk between "public models" and runtime models. |
| F4 | Medium | Security/observability | Roadmap sync logs content previews (first 1000 + last 500 chars) when ghost sections are detected. | Potentially leaks sensitive planning content into logs; high-noise "CRITICAL" logs reduce signal. |
| F5 | Medium | Docs/runtime alignment | README states "27 public MCP tools", while code contains at least 29 tool decorators in `src/cortex/tools/`. | External expectations and internal reality diverge; affects trust and onboarding. |
| F6 | Medium | Tooling coherence | `pyproject.toml` keeps strict mypy config while the documented and automated typecheck path is pyright (`make typecheck`, docs). | Dual-config maintenance overhead; unclear source-of-truth for type policy. |
| F7 | Low | Maintainability | Multiple modules exceed 550 lines. | Large files raise review difficulty and increase regression probability during edits. |

## Detailed findings and actions

### F1 — Contradictory troubleshooting guidance (High)

**Evidence**
- Troubleshooting says coverage is not in `pytest.ini` addopts.
- The same file later says `pytest.ini` sets `--cov-fail-under=90`.
- Actual `pytest.ini` addopts do not include coverage options.

**Action plan**
1. Fix the contradictory "Cause" section in `docs/guides/troubleshooting.md` to match current config.
2. Add a short doc-test checklist item: whenever `pytest.ini` changes, verify troubleshooting snippets.
3. Add a CI docs-consistency check (grep-based) for coverage guidance statements.

**Suggested owner**: documentation maintainer.
**Effort**: 1–2 hours.

### F2 — Broad TODO exclusion patterns can skip production files (High)

**Evidence**
- Exclusion uses generic regex patterns (`test`, `example`, `sample`, `demo`) against full path strings.
- A file like `src/contest/runner.py` or `src/latest_metrics.py` could match unintentionally.

**Action plan**
1. Replace substring regex matching with path-segment-aware rules:
   - Exclude test directories (`tests/`, `test/`) and explicit filename patterns (`test_*.py`, `*_test.py`).
   - Avoid generic substring checks in arbitrary path segments.
2. Add regression tests for "non-test files containing test-like substrings".
3. Optionally expose exclusions as configurable patterns with defaults documented.

**Suggested owner**: validation/tooling maintainer.
**Effort**: 0.5–1 day.

### F3 — Duplicate roadmap sync model layers (Medium)

**Evidence**
- `src/cortex/validation/roadmap_models.py` defines `TodoItemModel`, `RoadmapReferenceModel`, `SyncValidationResultModel`.
- `src/cortex/validation/roadmap_sync.py` defines `TodoItem`, `RoadmapReference`, `SyncValidationResult` with additional fields.

**Action plan**
1. Define a single canonical model set (prefer domain runtime models).
2. Make `validation/models.py` re-export the canonical classes directly.
3. Deprecate/remove duplicate model definitions after compatibility window.
4. Add unit tests to ensure tool responses match documented schema exactly.

**Suggested owner**: validation architecture owner.
**Effort**: 1–2 days.

### F4 — Over-verbose roadmap logging may leak sensitive context (Medium)

**Evidence**
- On ghost section detection, logs include long roadmap content previews.
- Log level used is `error` with "CRITICAL" wording for a recoverable/diagnostic condition.

**Action plan**
1. Remove full content previews from logs; log only metadata (path, size, section names found).
2. Downgrade level to warning unless actual data corruption is proven.
3. Add a privacy/logging rule test preventing full Memory Bank content in logs.

**Suggested owner**: security + observability owner.
**Effort**: 0.5 day.

### F5 — README tool count drift (Medium)

**Evidence**
- README claims 27 public MCP tools.
- Code scan shows at least 29 tool decorators under `src/cortex/tools/`.

**Action plan**
1. Replace hard-coded tool count with generated count or remove fixed number.
2. Add lightweight CI check that compares README count (if present) with discovered registrations.
3. Link to API docs as source of truth where possible.

**Suggested owner**: docs + API maintainers.
**Effort**: 1–3 hours.

### F6 — Type-checking strategy not explicit (Medium)

**Evidence**
- `pyproject.toml` includes strict `[tool.mypy]` config.
- Operational commands/docs use pyright (`make typecheck`, docs/releasing references pyright).

**Action plan**
1. Decide primary checker policy: pyright-only or dual-checker.
2. If pyright-only: remove stale mypy config and references.
3. If dual: add mypy to quality pipeline and ensure both configs are maintained intentionally.
4. Document the decision in contributing docs.

**Suggested owner**: tooling maintainer.
**Effort**: 0.5 day.

### F7 — Large-module concentration (Low)

**Evidence**
- Several modules are 550–617 lines.

**Action plan**
1. Prioritize top 5 largest modules for incremental extraction.
2. Introduce soft thresholds (e.g., warn >450 lines, review required >600 lines).
3. Track module size trend quarterly.

**Suggested owner**: architecture/code health owner.
**Effort**: ongoing (incremental).

## 30/60/90 day remediation plan

### Next 30 days

- Fix F1, F2, F4 immediately (high-value, low effort).
- Patch README tool-count drift (F5).
- Publish explicit type-checker decision draft (F6).

### 60 days

- Complete F3 model consolidation.
- Add CI/doc consistency checks for coverage and tool-count claims.

### 90 days

- Execute first wave of large-module refactoring (F7).
- Review metrics: false-positive/false-negative rates in roadmap sync, docs issue recurrence, logging hygiene incidents.

## Success metrics

- 0 contradictory docs sections for test/coverage policy.
- 0 known false-negative TODO cases from path-substring exclusions.
- Single canonical roadmap sync model family.
- No log output containing raw Memory Bank content snippets.
- README/API docs auto-aligned for tool inventory.

## Appendix: commands used during review

- `rg --files -g 'AGENTS.md'`
- `rg --files | head -n 200`
- `sed -n '1,240p' pyproject.toml`
- `make check`
- `uv sync --extra dev`
- `sed -n '1,260p' README.md`
- `sed -n '1,240p' src/cortex/validation/roadmap_models.py`
- `sed -n '1,520p' src/cortex/validation/roadmap_sync.py`
- `sed -n '1,220p' src/cortex/tools/validation/roadmap_sync.py`
- `sed -n '1,260p' pytest.ini`
- `sed -n '240,320p' docs/guides/troubleshooting.md`
- `python - <<'PY' ...` (module/file count and size checks)
- `python - <<'PY' ...` (tool decorator count)
