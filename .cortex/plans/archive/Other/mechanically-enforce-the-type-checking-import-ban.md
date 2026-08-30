---
title: "Mechanically Enforce the TYPE_CHECKING Import Ban"
component: "quality-gate"
work_type: infrastructure
status: PENDING
priority: Medium
created: 2026-08-02
depends_on: []
---

## Goal

Add a mechanical check to the quality gate that rejects `from typing import TYPE_CHECKING` and `if TYPE_CHECKING:` in `src/` and `tests/`, so the existing Synapse rule is enforced by tooling rather than by reviewer attention.

## Context

`python-coding-standards.mdc` forbids the `TYPE_CHECKING` pattern in three separate places, twice marked STRICTLY FORBIDDEN. Despite that, a violation was introduced into `src/cortex/tools/plans/step_plan_workflow.py` during the 2026-08-02 do-loop and passed every automated check: pyright, `ruff check`, `ruff format`, the structural gate, the review gate, and a 7,464-test suite. The user caught it by hand.

The rule was documented and ignored. Nothing in the toolchain looks for it, so the only enforcement was an agent remembering to read and apply a rule buried in a 500-line standards file. That is not enforcement.

The specific violation also shows the rule's rationale holds: the banned block carried a comment claiming an import-time cycle, but `crud.py` imports `step_plan_workflow` only lazily inside functions, so no module-level cycle existed. The workaround was unnecessary — exactly the code smell the rule predicts.

## Scope

**in_scope**

- A check that flags `from typing import TYPE_CHECKING` and `if TYPE_CHECKING:` under `src/` and `tests/`
- Wiring the check into the existing structural/quality gate so it fails the gate
- A clear failure message citing the rule and naming the file and line
- An allowlist mechanism for a genuinely unavoidable case, requiring an inline justification comment
- Tests covering detection, the allowlist, and clean code

**out_of_scope**

- Removing the now-dead `if TYPE_CHECKING:` coverage-exclusion entries in `pytest.ini` and `pyproject.toml` (harmless; separate cleanup)
- Auditing or rewriting other documented-but-unenforced rules
- Changing the rule text itself — the rule is already clear
- Any `.cortex/synapse/` rule-file edits

## Approach

Prefer configuration over new code. Ruff's `flake8-tidy-imports` `banned-api` setting can reject `typing.TYPE_CHECKING` by name with a custom message, which gets enforcement for near-zero maintenance and surfaces in the editor as well as in CI. Verify that it catches both the import form and, if not, add a narrow complementary check for the bare `if TYPE_CHECKING:` block form.

Fall back to a small check in the existing structural gate only if ruff configuration cannot cover both forms. Keep the failure message actionable: name the file, the line, and the rule, and state the usual correct fix (a normal top-level import, since the cited cycle is usually not real).

Allowlisting should be deliberately awkward — an inline justification comment, not a bare `noqa` — so that bypassing costs more than fixing.

## Implementation Steps

1. Confirm the current violation count is zero (`step_plan_workflow.py` was already fixed) so the check starts from a green baseline.
2. Add `typing.TYPE_CHECKING` to ruff's `flake8-tidy-imports.banned-api` in `pyproject.toml` with a message citing `python-coding-standards.mdc`.
3. Run `ruff check` across `src/` and `tests/`; confirm it flags the import form and record whether it also flags a bare `if TYPE_CHECKING:` with no import.
4. If step 3 leaves the block form uncovered, add a narrow detection for it to the existing structural gate.
5. Define the allowlist mechanism: an inline justification comment on the same line, with the reason recorded.
6. Verify the check fires by temporarily reintroducing the pattern in a scratch file, then removing it.
7. Add tests: violation detected (both forms), allowlisted violation passes, clean file passes.
8. Run the full quality gate and the full test suite until clean.

## Verification Checklist

- Step 2-3: grep `pyproject.toml` for the banned-api entry; run `ruff check` and read the actual output rather than assuming coverage.
- Step 4: confirm no duplicate detection — if ruff already covers a form, do not add a second check for it.
- Step 6: this is the load-bearing verification. A gate that cannot be shown to fail on a real violation is not verified.
- Step 7: confirm the allowlist test asserts the justification comment is required, not merely that a bypass exists.
- After all steps: `rg -n 'TYPE_CHECKING' src/ tests/` returns only allowlisted lines, if any.

## Dependencies

None.

## Success Criteria

- Reintroducing `from typing import TYPE_CHECKING` into any file under `src/` or `tests/` fails the quality gate
- The failure message names the file, the line, and the rule
- A bare `if TYPE_CHECKING:` block with no matching import is also caught
- An allowlisted occurrence requires an inline justification comment to pass
- `rg -n 'TYPE_CHECKING' src/ tests/` returns only allowlisted lines
- Full quality gate and full test suite pass
- New code paths reach the 95% coverage target

## Testing Strategy

Target 95% coverage on changed lines, AAA pattern.

- Unit — positive detection: file with `from typing import TYPE_CHECKING`; file with a bare `if TYPE_CHECKING:` block; file with both.
- Unit — negative: clean file passes; a file containing the literal string `TYPE_CHECKING` only inside a comment or docstring is not flagged.
- Unit — allowlist: occurrence with a justification comment passes; occurrence with a bare suppression and no justification still fails.
- Integration: the gate as a whole fails when a violation is present and passes when it is not.
- Baseline: the current repository passes with zero violations.

## Risks and Mitigation

| Risk | Impact | Mitigation |
|------|--------|------------|
| Ruff's banned-api misses the bare block form | Half the rule stays unenforced | Step 3 explicitly records actual output; step 4 adds complementary detection only if needed |
| False positives on the string in comments or docstrings | Gate noise; pressure to disable it | Negative test covers comment and docstring occurrences |
| A genuine circular import someday needs the pattern | Contributor is hard-blocked | Allowlist with mandatory inline justification — awkward on purpose, not impossible |
| Duplicate detection between ruff and the structural gate | Two error messages for one problem | Verification checklist explicitly checks for duplication before adding the second check |
| Check added but never proven to fire | False confidence; same failure as today | Step 6 requires demonstrating a real failure before the plan can be marked complete |

## Change History

_No revisions recorded yet — enrich or edit implementation steps to append history._
