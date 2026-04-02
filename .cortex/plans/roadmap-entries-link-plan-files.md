---
title: "Roadmap entries: link to plan files"
component: cortex-mcp
work_type: tooling
status: PENDING
priority: normal
created: 2026-04-01
depends_on: []
---

## Goal

Make **pending roadmap bullets** reliably include a **machine- and human-usable pointer** to the corresponding file under `.cortex/plans/`, so agents and `session()` / next-work logic are not forced to guess from title text alone.

## Context

- `plan(operation="register")` builds lines via `_build_entry_text` as `- **{title}** - {status} - {description}` only (`register_helpers.py`). It does **not** append `Plan: …` unless callers embed it in `description`.
- `extract_plan_path_from_bullet` already recognizes `Plan: <path>` for deduplication; `docs/api/tools.md` shows embedding the path in `description` as a workaround.
- `extract_next_work_item` / `_process_pending_line` in `start_tools.py` optionally captures `Plan: <path>` after the description (regex expects `… description. Plan: path`).
- Risk: title-only bullets are ambiguous when multiple plans share themes or when the implement command needs an explicit `@.cortex/plans/...` target.

## Implementation Steps

### Step 1: Extend MCP `plan(register)` / `register_plan_in_roadmap`

- Add an optional parameter **`plan_file_name`** (basename only, e.g. `cleanup-synapse-prompt-filenames-do-plan.md`) or **`plan_relative_path`** (preferred single representation: always `.cortex/plans/<file>.md`).
- When provided, append to the rendered bullet a stable fragment matching session parsing: e.g. end the description segment with `Plan: .cortex/plans/<file>.md` (confirm exact punctuation against `_process_pending_line` regex — today it expects a **period before `Plan:`**).
- Update `PlanRegisterPayload` in `plan_payloads.py` and the plan tool dispatcher (`plan.py`) to pass the new field through.
- Keep **backward compatibility**: omitting the field preserves current behavior; document that new Plan prompt runs should supply it.

### Step 2: Wire create → register (optional consolidation)

- Where `plan(operation="create")` returns `file_path` / filename, document or automate that the next `plan(operation="register", …, plan_file_name=…)` uses that value so agents do not hand-copy paths.

### Step 3: Synapse prompt + compliance tests

- Update **Plan** prompt Step 8: require passing the plan file path into registration (via new parameter or embedded `Plan:` in description if parameters are stripped).
- Extend **`tests/integration/test_plan_creation_workflow_compliance.py`** (or equivalent) so the prompt text mandates plan-path registration.
- Add unit/integration tests for `_build_entry_text` / `register_plan_entry` when `plan_file_name` is set: roadmap line contains `Plan: .cortex/plans/…` and `extract_plan_path_from_bullet` returns the path.

### Step 4: Documentation

- Update `docs/api/tools.md` **plan(register)** section: first-class `plan_file_name` (or path) parameter; adjust examples to show the recommended one-liner without duplicating path inside free-form `description`.
- Short note in `docs/guides/workflows.md` if it describes Plan prompt registration.

### Step 5 (optional): Lint or docs-gate hint

- Consider a **non-blocking** warning in roadmap validation when a `PENDING` line under pending plans lacks `Plan:` — or defer if noisy; document trade-off.

## Verification Checklist

| Step | What to search for | Search scope | Files to re-read |
|------|-------------------|--------------|------------------|
| 1 | `plan_file_name`, `_build_entry_text` | `src/cortex/tools/plans/` | `register_helpers.py`, `register.py`, `plan.py`, `plan_payloads.py` |
| 2 | `operation="register"` | `tests/` | integration tests for plan tool |
| 3 | `Step 8`, `register` | `.cortex/synapse/prompts/plan.md` | prompt + compliance test |
| 4 | `plan(operation="register"` | `docs/api/tools.md` | tools.md |

## Dependencies

- None blocking; Synapse submodule edit for `plan.md` after Cortex code ships (or coordinate submodule bump).

## Testing Strategy

- Unit tests for `_build_entry_text` / register path with `plan_file_name`; integration tests for `plan(operation="register")` JSON round-trip.
- Prompt compliance test updated for Step 8.
- Target **≥95%** coverage on touched modules where practical.

## Success Criteria

- New registrations can include a **canonical plan path** without manual `description` hacks.
- Session/orchestrator code paths that read `Plan:` continue to work.
- Plan prompt workflow text and tests align with the new parameter.

## Partial Progress Log

- 2026-04-02: Added optional canonical register path support via `plan_relative_path` across plan payloads/dispatcher/register rendering with regression tests for emitted `Plan: .cortex/plans/...` bullets — files: src/cortex/tools/plans/plan_payloads.py, src/cortex/tools/plans/plan.py, src/cortex/tools/plans/register.py, src/cortex/tools/plans/register_helpers.py, tests/integration/test_structured_plan_tools.py, tests/tools/test_plan_payloads.py
