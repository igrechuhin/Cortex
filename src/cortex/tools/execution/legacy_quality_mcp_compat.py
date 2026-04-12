"""Sunset marker for legacy quality MCP entrypoints.

DEPRECATED: remove by 2026-07-01. Migrate callers to run_quality_gate() and autofix().

The MCP tools ``execute_pre_commit_checks``, ``start_quality_job``, and
``get_quality_job_status`` are still registered from ``pre_commit_tools`` until
the sunset date. Internal Phase A preflight now uses the same detached runner as
``run_quality_gate`` (see ``run_detached_phase_a_checks``). CI asserts this module
keeps the removal annotation so the date is not forgotten.
"""

LEGACY_QUALITY_SUNSET_ISO = "2026-07-01"

__all__ = ["LEGACY_QUALITY_SUNSET_ISO"]
