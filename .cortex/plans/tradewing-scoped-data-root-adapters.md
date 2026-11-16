---
status: PENDING
---

# TradeWing scoped data root and reader adapters

## Status

PENDING. Planning only; no installation, restart, access activation, TradeWing source change, production preparation, training, or data migration is authorized.

## Evidence and goal

The [historical connection plan](https://github.com/igrechuhin/Cortex/blob/2fae2c233ee60c3eb15a178df348e53e94a22bb6/docs/guides/tradewing-connection-plan.md) describes the retired feature; it is not part of current Cortex. TradeWing_Data is a sibling of the project root; the v6 destination must be new, profile payloads use the existing compressed reader, and live progress is printed to stdout. The confirmed v6 command materializes a partial archive and does not certify complete profiles.

## Proposed work after approval

1. Verify the exact visible TradeWing chat's existing Cortex command, source revision, canonical root and whether configuration is shared. Stop on a mismatched root or effects on other active chats.
2. Design an optional explicit data root with independent exact read/write allowlists, canonical path/descriptor protections, secret exclusions, strict size bounds and an external owner-approved hash pin. Preserve the project root; do not widen to the repositories parent or use symlinks.
3. Wrap the existing reader and preparation entrypoint without duplicating exporter calculations. Reconcile new-child output-directory creation, BLOB decoding through the original reader, bounded full JSON output, and allowlisted structured progress. Seal code/interpreter/dependencies only after the preparation owner declares a stable boundary.
4. Keep the 14-tool surface, disabled defaults, no arbitrary shell/SQL/argv, finite parameters, exclusive reservations and no retry after uncertain execution.
5. Validate only synthetic sibling-root fixtures and harmless jobs; preserve the existing fixture suite. Do not reuse working preparation or migration outputs as test fixtures.
6. Obtain separate concrete owner approval before any target-chat installation/reconnection and fixture-only policy activation. Keep working datasets/jobs disabled until all blockers and their separate approvals are resolved.

## Acceptance

Fresh Cortex quality/docs gates pass; negative tests cover both roots and escapes. Existing reader output remains original, gaps and incomplete status remain visible, and no complete-profile command or working-data approval is invented. The connection guide gives a bounded smoke test and rollback. No TradeWing production operation is part of this Cortex plan.

## Change History

_No revisions recorded yet — enrich or edit implementation steps to append history._
