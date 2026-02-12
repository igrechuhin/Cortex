# Git Operations Guide

This guide covers Git usage in the context of the Cortex commit pipeline and common issues.

## Commit pipeline and push

The commit workflow (e.g. `/cortex/commit`) creates a commit locally (Step 13) and then pushes the branch (Step 14). Push is a **post-commit** step: the commit exists on your machine even if push fails.

## Push failures and SSL

If **Step 14: Push branch** fails with an SSL certificate error (for example `unable to get local issuer certificate` or `self signed certificate in certificate chain`):

1. **Commit is not lost** – the commit was already created in Step 13.
2. **Retry**: The commit pipeline may retry push up to 2 times on SSL/certificate errors before giving up.
3. **Fix SSL** – follow the [Git and SSL Certificate Issues](./troubleshooting.md#git-and-ssl-certificate-issues) section in the Troubleshooting guide.
4. **Push manually** after fixing:

   ```bash
   git push origin <branch-name>
   ```

Push can also fail due to network timeouts, authentication, or permissions. In all cases, the local commit remains; fix the underlying issue and push again. The commit prompt treats push as **non-blocking** for pipeline success: completing through Step 13 is a successful commit; Step 14 is best-effort push.

## References

- [Troubleshooting guide](./troubleshooting.md) – SSL certificate verification, auth, and other Git issues
- [Commit pipeline phases](../design/commit-pipeline-phases.md) – Phase-based commit workflow
- [Getting started](../getting-started.md) – Initial setup and pre-commit hooks
