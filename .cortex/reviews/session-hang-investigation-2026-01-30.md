# Session Hang Investigation – 2026-01-30

## Context

User reported that an agent session "seemed like hanged." The transcript for that session was analyzed to determine where and why it stopped making progress.

## Transcript Summary

- **Session**: Commit workflow (`user-cortex/commit`).
- **Flow**: Steps 0–1.5 completed (fix errors, format, markdown lint). Steps 2–3 (type check, quality) passed. Step 4 (tests) ran via `execute_pre_commit_checks(checks=["tests"], timeout=300, coverage_threshold=0.9)`.
- **Step 4 outcome**: Tests passed (2919, 0 failed) but **coverage was 89.98%**, below the 90% threshold. The MCP tool correctly returned `success: false` for tests due to coverage.
- **Agent response**: Agent correctly blocked commit and tried to fix coverage by running a **Shell** command to get a coverage report:
  1. First Shell: `pytest --cov=src/cortex --cov-report=term-missing --cov-fail-under=90 -q 2>&1 | tail -80`. Agent inferred "The test run timed out" (so the first Shell likely timed out or returned an error).
  2. Second Shell: Same project, `pytest --cov=... --cov-fail-under=89 -q --timeout=300 2>&1 | tail -120` with **timeout: 360000** (6 minutes).
- **Transcript end**: The log ends with `[Tool result] Shell` for the second Shell call. There is **no subsequent assistant message or tool call**.

So from the transcript we know:

1. The second Shell **did** return (the result marker is present).
2. After that result, the agent was expected to analyze the coverage report and either fix coverage or document an exception—but no such turn appears.
3. From the user’s perspective, the session "hung" either while waiting for the Shell or after the Shell returned with no further agent output.

## Root Cause Analysis

### 1. Most likely: Shell run duration + no follow-up

- The second Shell runs the **full pytest suite with coverage** (`--cov-report=term-missing`). For ~2919 tests this can take **several minutes** (often 3–6+ minutes).
- If the Shell was still running when the user looked, the session would appear "hung" with no visible progress.
- If the Shell completed, the **output can be very large** (term-missing lists uncovered lines for many files). That could:
  - Truncate in the tool result, or
  - Push the conversation near context limits so the next model turn failed or was dropped.

So the hang is likely a combination of: (a) long wait for the Shell, and (b) no assistant turn after the Shell result (due to timeout, truncation, or context limits).

### 2. Sandbox / timeout behavior

- The first Shell had no explicit `timeout` in the transcript; default sandbox limits (e.g. 30s) would likely kill it before pytest+coverage finishes.
- The second Shell requested `timeout: 360000` (6 min). If the sandbox enforces a lower cap, the command could still be killed; the agent would then get a timeout error and might not have produced a clear next step.

### 3. Commit workflow and coverage

- Coverage was **89.98%**, just below 90%. The commit workflow correctly blocked.
- The agent chose to run **full pytest + coverage** in a Shell instead of, for example:
  - Using an MCP or script that returns a **short** coverage summary or only the lowest-covered files, or
  - Running coverage on a subset (e.g. one package) to get a small report quickly.

So the choice of tool (full Shell pytest with term-missing) made long run time and large output more likely, increasing the chance of perceived hang or missing follow-up.

### 4. Why the agent ran tests directly instead of using the script

- **Step 4** correctly used `execute_pre_commit_checks(checks=["tests"], ...)` (MCP tool). The commit prompt says tests are run via MCP; the script (`.cortex/synapse/scripts/python/run_tests.py`) is only mentioned as the **fallback** for Step 12.4.1 (re-run tests).
- When coverage failed (89.98%), the prompt says "fix coverage first" and "re-run tests" but **does not** say "use `run_tests.py` or MCP for any test/coverage run; do not run raw pytest in a Shell."
- The agent then tried to get a **detailed coverage report** (uncovered lines) to know what to fix. The MCP tool returns a summary (e.g. `results.tests.coverage`), not a line-by-line report. So the agent improvised and ran **raw pytest** in a Shell with `--cov-report=term-missing`, bypassing both the MCP tool and the script.
- **run_tests.py** uses `--cov-report=xml` and `--cov-report=term` (not term-missing), has a single timeout (300s), and is the canonical way to run tests. Using it would have kept behavior consistent and avoided ad-hoc pytest invocations.

So the agent ran tests directly because the commit prompt never directs the "fix coverage" flow to use the script (or to avoid raw pytest); the agent chose raw pytest to get a term-missing report the MCP doesn't provide.

## Recommendations

1. **Avoid full pytest+coverage in Shell for “find coverage gap”**  
   Prefer:
   - A script or MCP that returns only coverage summary + lowest-covered modules (e.g. top N files or packages below 90%), or
   - Running coverage on a subset of tests/packages when the goal is to identify a small gap (e.g. 89.98% → 90%).

2. **Commit / agent docs**  
   In commit workflow or agent instructions:
   - When coverage is just below 90%, suggest “run coverage summary or low-coverage report” rather than “run full pytest with term-missing.”
   - Optionally suggest using existing `.cortex/synapse/scripts/python/` helpers if they expose a short coverage report.

3. **Session/stdio**  
   If "hang" reports continue after Shell or MCP steps, consider:
   - Cursor/sandbox timeout for long-running Shell commands.
   - Limiting or summarizing very large tool outputs (e.g. coverage) so the model always gets a bounded response and can reliably produce a next turn.

## References

- Transcript: `agent-transcripts/3d5286b4-f4dd-4959-8004-33ac1f042f25.txt`
- Related: `.cortex/reviews/tool-hang-investigation-2026-01-29.md` (commit workflow hang after `fix_markdown_lint`)
- Commit workflow: `/cortex/commit`, Steps 4 (tests) and coverage threshold 90%
- execute_pre_commit_checks: `timeout=300`, `coverage_threshold=0.9`
