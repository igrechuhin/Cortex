# Lint Config

Use `.cortex/config/lint-config.json` to tune the `.cortex/synapse/prompts/lint-wiki.md` workflow.

## Schema

```json
{
  "code_claim_checks": [
    {
      "file": ".cortex/memory-bank/techContext.md",
      "pattern": "python",
      "verify_against": "pyproject.toml"
    }
  ],
  "stale_threshold_days": 30
}
```

## Fields

- `code_claim_checks`: List of claim rules for `CodeClaimCheck`.
- `code_claim_checks[].file`: File containing documented claims to verify.
- `code_claim_checks[].pattern`: Regex used to locate claim lines in `file`.
- `code_claim_checks[].verify_against`: Source-of-truth file for comparisons.
- `stale_threshold_days`: Age threshold for `StaleActiveContextCheck` (must be `>= 1`).

## Behavior Notes

- If `.cortex/config/lint-config.json` is missing, lint uses defaults.
- If config is malformed, lint safely falls back to defaults/no-op behavior.
- Paths can be project-relative (for example `pyproject.toml`) or `.cortex/...`.
