## Goal
Implement end-to-end Swift coverage collection and threshold enforcement so `results.tests.coverage` is populated and the existing 90% gate is enforced for Swift runs.

## Context
Current Swift quality runs execute tests but return `coverage=None`, which prevents true threshold enforcement. Recent prompt updates changed reporting semantics from `0.0%` to `N/A`, but enforcement parity still requires real Swift coverage extraction and gate wiring.

## Scope
### in_scope
- Add Swift test invocation and parsing flow that yields numeric coverage in `TestResult.coverage`.
- Ensure pre-commit / quality-gate pipeline uses Swift coverage value for pass/fail against configured threshold.
- Add/adjust tests for Swift adapter coverage parsing and pipeline threshold behavior.
- Update docs/prompts where they currently imply Swift coverage is unavailable.

### out_of_scope
- Rewriting non-Swift adapters.
- Changing global default threshold value.
- Broad refactors unrelated to coverage collection/enforcement.

## Implementation Steps
1. Define Swift coverage extraction contract.
   - Decide canonical source (`swift test --enable-code-coverage` + supported report path/tooling).
   - Specify failure modes (missing coverage artifacts, parse failures) and deterministic error/warning behavior.

2. Implement Swift adapter coverage collection.
   - Update Swift adapter test execution to request coverage artifacts.
   - Parse coverage percentage into normalized fraction for `TestResult.coverage`.
   - Preserve robust output decoding/error handling.

3. Wire threshold enforcement in shared pipeline path.
   - Ensure Swift test results participate in existing `coverage_threshold` checks.
   - Prevent silent pass when tests succeed but coverage is below threshold.

4. Add test coverage for new behavior.
   - Unit tests for Swift coverage parsing (valid, missing, malformed).
   - Pipeline tests for pass/fail threshold outcomes using Swift adapter results.

5. Update docs/prompt references.
   - Replace stale notes that imply Swift coverage is inherently unavailable.
   - Document expected payload shape and `N/A` vs numeric behavior.

## Verification Checklist
- Step 1: What to search for | `coverage contract`, `swift test --enable-code-coverage`, `TestResult.coverage` | Search scope `src/cortex/services/framework_adapters`, `src/cortex/tools/execution`, `.cortex/synapse/prompts`
- Step 2: What to search for | `SwiftAdapter.run_tests`, `coverage`, `llvm-cov` or Swift coverage parser paths | Search scope `src/cortex/services/framework_adapters/swift_adapter.py`
- Step 3: What to search for | `coverage_threshold`, `build_test_errors`, pipeline test-result handling | Search scope `src/cortex/tools/execution`, `src/cortex/services/framework_adapters`
- Step 4: What to search for | `test_swift_adapter`, `coverage`, threshold assertions | Search scope `tests/unit`, `tests/services`, `tests/tools`
- Step 5: What to search for | `N/A`, `Swift coverage`, commit/report wording | Search scope `.cortex/synapse/prompts`, docs

## Dependencies
- Existing Swift adapter execution path and pre-commit pipeline result schema.
- Availability of Swift coverage artifacts/commands in the runtime environment.

## Success Criteria
- `results.tests.coverage` is numeric for successful Swift test runs where coverage data exists.
- Swift runs fail gate when numeric coverage is below configured threshold.
- Tests verify parser correctness and threshold enforcement regressions.
- Prompt/docs reflect parity behavior accurately.

## Testing Strategy (95% coverage target)
- Add focused unit tests for parser branches and error handling to keep new code paths at >=95% coverage.
- Add pipeline-level assertions for threshold pass/fail behavior with Swift test results.
- Include negative-path tests (missing artifacts, malformed output) to prevent false positives.

## Change History

_No revisions recorded yet — enrich or edit implementation steps to append history._
