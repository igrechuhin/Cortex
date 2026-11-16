# Changelog

This file records release changes for Cortex. Versions follow semantic versioning.

## 1.2.0 — Unreleased

This release is prepared for review. Required verification and publication remain
pending; no release date or successful installation is claimed.

### Added

- Optional paired uv cache and tool directories for generated plugin packages,
  applied consistently to MCP and SessionStart commands. Existing default commands
  and GitHub or wheel sources remain supported.
- A safe Project Access summary at session startup, with actionable configuration
  reasons and an explicit indication that planning does not require its policy.

### Fixed

- Quality runs distinguish an owner's existing request from another session's
  active run. A checkout lease prevents concurrent test processes across server
  processes and remains guarded while live test descendants exist.
- The Markdown gate can use the approved installed, pinned rumdl executable
  without the shared uv cache, verifying dependency provenance and preserving
  genuine lint failures.
- Real packaged and generated-plugin protocol fixtures use test-owned uv state.
  Bounded, redacted startup diagnostics keep child stderr separate from MCP stdout.

### Changed

- Package, runtime and editable lock metadata are aligned at 1.2.0, following the
  existing GitHub release series whose previous published release is 1.1.1.

### Release references

- [Previous published release: 1.1.1](https://github.com/igrechuhin/Cortex/releases/tag/1.1.1)
- [Release procedure](docs/development/releasing.md)
- [Plugin launch configuration](docs/guides/plugins.md)
- [Project Access behavior](docs/guides/project-access.md)
