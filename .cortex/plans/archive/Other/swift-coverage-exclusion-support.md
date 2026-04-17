# Swift Coverage Exclusion Support

## Problem

TradeWing coverage gains are being masked because Cortex aggregates SwiftPM coverage across generated protobuf files (`*.pb.swift`) and other non-actionable generated sources. Current Swift coverage handling is inconsistent:

- `swift_coverage.py` JSON aggregation skips only `.build` and `Tests` paths.
- `SwiftAdapter._llvm_cov_report_argv()` hardcodes `-ignore-filename-regex=.build|Tests`.
- There is no Cortex-level configuration surface for project-specific coverage exclusions.
- This forces downstream projects to accept misleading coverage metrics or maintain ad hoc local workarounds outside Cortex.

## Goal

Add first-class Cortex support for Swift coverage exclusions so external projects can declare ignore patterns once and have them applied consistently in local runs and CI-backed Cortex workflows.

## Scope

1. Introduce a project-configurable coverage exclusion surface for Swift projects.
2. Apply exclusions consistently to both SwiftPM JSON aggregation and `llvm-cov` fallback paths.
3. Preserve current default exclusions (`.build`, `Tests`) while allowing extra project-specific patterns such as `*.pb.swift`.
4. Add focused adapter and coverage-parser tests for generated-file exclusion behavior.
5. Document how external projects opt in via Cortex-managed config.

## Notes

- TradeWing is the motivating case: generated protobuf sources should not count against effective coverage.
- Exclusion should live in Cortex first; TradeWing config should become a thin consumer of the new capability.
- Prefer project-level patterns over hardcoded TradeWing-specific logic.

## Success Criteria

- Cortex exposes a documented way to declare Swift coverage exclusion patterns.
- JSON and llvm-cov coverage calculations respect the same exclusion set.
- `*.pb.swift` can be excluded without patching project-specific scripts.
- Regression tests cover both default and custom exclusion behavior.

## Change History

- **2026-04-16**: Implemented optional ``.cortex/config/swift_coverage.json`` with ``exclude_filename_regex_patterns`` (max 32, each ≤256 chars). JSON codecov aggregation and ``llvm-cov report`` fallback both apply the same patterns plus built-in ``.build`` / ``Tests`` skips. Cortex repo ships an empty example config; TradeWing can add e.g. ``\\.pb\\.swift$`` and ``\\.grpc\\.swift$``.
