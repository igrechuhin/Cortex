# Rebind Local Environment Context

Regenerate the local machine-context artifact for the current host.

## Steps

1. Resolve the current workspace root via `roots/list`.
2. Delete `.cortex/memory-bank/local-environment-context.json` in that root.
3. Call `session()` once to trigger startup housekeeping and artifact recreation.
4. Re-read `.cortex/memory-bank/local-environment-context.json` and confirm:
   - `machine_binding.host_fingerprint` matches current host details
   - `artifact.local_only` is `true`
   - `artifact.git_untracked` is `true`
5. Return a concise success/failure summary and include remediation if recreation failed.

## Notes

- Use this only when startup reports a local environment binding mismatch.
- This prompt is safe and idempotent: rerunning it rewrites only the local artifact.
