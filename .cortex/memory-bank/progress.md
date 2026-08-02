# Progress Log

## 2026-08-02

- **Shaping Interview Prompt (shape.md) Before Plan** - COMPLETE. Added shape.md prompt + shape-interviewer subagent for one-question-at-a-time requirements shaping; threaded shape_log_path through plan(create) to inject "## Shaping Constraints"; extended plan.md Step 4 into a four-route gate; added shared plan-log path validation guarding both shape and explore log paths. 17 new tests.
- **Shared Prompt Reference Layer for Synapse Prompts** - COMPLETE (negative result). Duplication measurement gated the plan: 0.19% extractable vs a 15% abort floor, so no _shared/ layer or include resolver was built. Delivered scripts/measure_prompt_duplication.py (standing measurement tool), tests/unit/test_measure_prompt_duplication.py (15 tests), and docs/design/synapse-prompt-duplication-report.md. Confirmed the REFACTORING_GUIDE/SUMMARY relocation to docs/guides/ was already done with no stale references.
- **Domain Glossary Consistency Gate in Plan Creation** - COMPLETE. Added canonical .cortex/wiki/glossary.md (30 curated terms) and an advisory-only terminology gate in plan creation covering exactly three detection cases; wired into both fast-forward and step-by-step planning modes, with a Terminology row in the /cortex/plan final report. 47 tests added; full suite 7464 passed.
- **Mechanically Enforce the TYPE_CHECKING Import Ban** - COMPLETE. Ruff TID251 banned-api in ruff.toml plus a complementary token-based source audit wired into the quality gate covering the bare `if TYPE_CHECKING:` block form and a justification-comment allowlist. Both layers verified to fire on a real violation. 16 tests, 100% coverage on new code, full suite green.

## 2026-07-23

- **Week containing 2026-07-23** - 9 entries summarized.

## 2026-07-22

- **Week containing 2026-07-22** - 3 entries summarized.

## 2026-07-21

- **Week containing 2026-07-21** - 4 entries summarized.

## 2026-07-20

- **Week containing 2026-07-20** - 12 entries summarized.

## 2026-07-19

- **Week containing 2026-07-19** - 1 entries summarized.

## 2026-06-30

- **Month containing 2026-06-30** - 2 entries summarized.

## 2026-06-25

- **Month containing 2026-06-25** - 10 entries summarized.

## 2026-06-24

- **Month containing 2026-06-24** - 5 entries summarized.

## 2026-06-23

- **Month containing 2026-06-23** - 5 entries summarized.

## 2026-05-08

- **Month containing 2026-05-08** - 4 entries summarized.

## 2026-05-04

- **Month containing 2026-05-04** - 2 entries summarized.

## 2026-05-03

- **Month containing 2026-05-03** - 5 entries summarized.

## 2026-04-29

- **Month containing 2026-04-29** - 1 entries summarized.

## 2026-04-27

- **Month containing 2026-04-27** - 2 entries summarized.

## 2026-04-26

- **Month containing 2026-04-26** - 2 entries summarized.

## 2026-04-25

- **Month containing 2026-04-25** - 2 entries summarized.

## 2026-04-24

- **Month containing 2026-04-24** - 2 entries summarized.

## 2026-04-23

- **Month containing 2026-04-23** - 3 entries summarized.

## 2026-04-22

- **Month containing 2026-04-22** - 2 entries summarized.

## 2026-04-20

- **Month containing 2026-04-20** - 5 entries summarized.

## 2026-04-21

- **Month containing 2026-04-21** - 6 entries summarized.

## 2026-04-19

- **Month containing 2026-04-19** - 3 entries summarized.

## 2026-04-18

- **Month containing 2026-04-18** - 4 entries summarized.

## 2026-04-17

- **Month containing 2026-04-17** - 6 entries summarized.

## 2026-04-16

- **Month containing 2026-04-16** - 14 entries summarized.

## 2026-04-15

- **Month containing 2026-04-15** - 11 entries summarized.

## 2026-04-14

- **Month containing 2026-04-14** - 18 entries summarized.

## 2026-04-13

- **Month containing 2026-04-13** - 6 entries summarized.

## 2026-04-12

- **Month containing 2026-04-12** - 21 entries summarized.

## 2026-04-11

- **Month containing 2026-04-11** - 1 entries summarized.

## 2026-04-10

- **Month containing 2026-04-10** - 1 entries summarized.

## 2026-04-09

- **Month containing 2026-04-09** - 1 entries summarized.

## 2026-04-08

- **Month containing 2026-04-08** - 1 entries summarized.

## 2026-04-07

- **Month containing 2026-04-07** - 1 entries summarized.

## 2026-04-06

- **Month containing 2026-04-06** - 1 entries summarized.

## 2026-04-04

- **Month containing 2026-04-04** - 1 entries summarized.

## 2026-04-03

- **Month containing 2026-04-03** - 1 entries summarized.

## 2026-04-02

- **Month containing 2026-04-02** - 1 entries summarized.

## 2026-04-01

- **Month containing 2026-04-01** - 1 entries summarized.

## 2026-03-31

- **Month containing 2026-03-31** - 1 entries summarized.

## 2026-03-30

- **Month containing 2026-03-30** - 1 entries summarized.

## 2026-03-29

- **Month containing 2026-03-29** - 1 entries summarized.

## 2026-03-28

- **Month containing 2026-03-28** - 1 entries summarized.

## What Works

Pre-commit pipeline (fix_errors, format, type_check, quality, tests); 6495 tests, 91.14% coverage (as of 2026-04-14); integration tests for projectBrief schema; Option C HTTP/SSE transport (Phase 1 and 2). Plan prompt and memory-bank-updater mandate register_plan_in_roadmap for new plan entry to prevent roadmap corruption.

## What's Left

See roadmap.md.
