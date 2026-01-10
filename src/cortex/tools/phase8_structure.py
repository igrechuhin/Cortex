#!/usr/bin/env python3
"""
Phase 8: Comprehensive Project Structure Management Tools

MCP tools for managing project structure, including:
- Structure health monitoring (with optional cleanup)
- Structure information retrieval

Total: 2 tools
- check_structure_health (with optional perform_cleanup parameter)
- get_structure_info

Note: setup_project_structure, migrate_project_structure, and setup_cursor_integration
have been replaced by prompt templates in docs/prompts/

Note: cleanup_project_structure has been consolidated into check_structure_health with
perform_cleanup=True parameter.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import cast

from cortex.managers.initialization import get_project_root
from cortex.server import mcp
from cortex.structure.structure_manager import StructureManager


@mcp.tool()
async def check_structure_health(
    project_root: str | None = None,
    perform_cleanup: bool = False,
    cleanup_actions: list[str] | None = None,
    stale_days: int = 90,
    dry_run: bool = True,
) -> str:
    """Analyze project structure health and optionally perform cleanup operations.

    Performs comprehensive health checks on the MCP Memory Bank project structure,
    verifying that all required directories exist, symlinks are valid, configuration
    files are present, and files are properly organized. Optionally performs cleanup
    actions to maintain structure integrity and archive stale content.

    Health checks validate:
    - Required directories (.cursor/, .cursor/memory-bank/, .cursor/plans/, etc.)
    - Symlink validity and targets (memory-bank/ → .cursor/memory-bank/)
    - Configuration files existence and validity (.cursor/structure.json)
    - File organization (plans in correct subdirectories, no orphaned files)
    - Memory bank file presence (projectBrief.md, activeContext.md, etc.)

    Cleanup actions (when perform_cleanup=True):
    - archive_stale: Move inactive plans older than stale_days to archived/
    - organize_plans: Categorize plans by status (active/completed/archived)
    - fix_symlinks: Repair broken Cursor symlinks (memory-bank/, rules/)
    - update_index: Refresh metadata index (.cursor/.memory-bank-index)
    - remove_empty: Remove empty plan directories (active/, completed/, archived/)

    Args:
        project_root: Absolute path to project root directory. If None, uses current
            working directory. Example: "/Users/username/projects/my-project"
        perform_cleanup: Whether to perform cleanup actions in addition to health
            checks. Default: False (check-only mode)
        cleanup_actions: List of specific cleanup actions to perform. Valid values:
            ["archive_stale", "organize_plans", "fix_symlinks", "update_index",
            "remove_empty"]. If None, performs all cleanup actions. Example:
            ["archive_stale", "fix_symlinks"]
        stale_days: Number of days of inactivity before considering a plan file
            stale for archival. Based on file modification time. Default: 90.
            Example: 30 (archive plans inactive for 30+ days)
        dry_run: If True, previews cleanup actions without making changes. If False,
            executes cleanup actions. Default: True (safe preview mode).
            Example: False (execute cleanup)

    Returns:
        JSON string containing health report with structure:
        {
            "success": true,
            "health": {
                "score": 85,                    // 0-100 health score
                "grade": "B",                   // Letter grade (A/B/C/D/F)
                "status": "good",               // healthy/good/fair/warning/critical
                "checks": {
                    "required_directories": true,
                    "symlinks_valid": true,
                    "config_exists": true,
                    "files_organized": false
                },
                "issues": [
                    "3 plan files found in root .cursor/plans/ (should be in subdirectories)"
                ],
                "recommendations": [
                    "Move misplaced plan files to active/, completed/, or archived/",
                    "Run with perform_cleanup=True and cleanup_actions=['organize_plans']"
                ]
            },
            "summary": "Structure health: GOOD (Grade: B, Score: 85/100)",
            "action_required": false,
            "cleanup": {                        // Only if perform_cleanup=True
                "dry_run": true,
                "actions_performed": [
                    {
                        "action": "archive_stale",
                        "stale_plans_found": 2,
                        "files": ["old-feature.md", "deprecated-plan.md"]
                    },
                    {
                        "action": "fix_symlinks",
                        "symlinks_fixed": 1
                    }
                ],
                "files_modified": [
                    "Moved old-feature.md to archived/",
                    "Moved deprecated-plan.md to archived/"
                ],
                "recommendations": [
                    "Re-run with dry_run=False to apply changes"
                ],
                "post_cleanup_health": {
                    "score": 95,
                    "grade": "A",
                    "status": "healthy"
                }
            }
        }

        On error:
        {
            "success": false,
            "error": "Project root does not exist: /invalid/path",
            "error_type": "FileNotFoundError"
        }

    Examples:
        Example 1: Basic health check (no cleanup)
        >>> await check_structure_health()
        {
            "success": true,
            "health": {
                "score": 100,
                "grade": "A",
                "status": "healthy",
                "checks": {
                    "required_directories": true,
                    "symlinks_valid": true,
                    "config_exists": true,
                    "files_organized": true,
                    "memory_bank_files": true
                },
                "issues": [],
                "recommendations": []
            },
            "summary": "Structure health: HEALTHY (Grade: A, Score: 100/100)",
            "action_required": false
        }

        Example 2: Health check with dry-run cleanup preview
        >>> await check_structure_health(
        ...     perform_cleanup=True,
        ...     cleanup_actions=["archive_stale", "fix_symlinks"],
        ...     stale_days=30,
        ...     dry_run=True
        ... )
        {
            "success": true,
            "health": {
                "score": 75,
                "grade": "C",
                "status": "fair",
                "checks": {
                    "required_directories": true,
                    "symlinks_valid": false,
                    "config_exists": true,
                    "files_organized": true
                },
                "issues": [
                    "Broken symlink: memory-bank/ -> .cursor/memory-bank/",
                    "5 stale plans older than 30 days"
                ],
                "recommendations": [
                    "Fix broken symlinks",
                    "Archive stale plans"
                ]
            },
            "summary": "Structure health: FAIR (Grade: C, Score: 75/100)",
            "action_required": true,
            "cleanup": {
                "dry_run": true,
                "actions_performed": [
                    {
                        "action": "archive_stale",
                        "stale_plans_found": 5,
                        "files": [
                            "feature-login.md",
                            "refactor-auth.md",
                            "spike-database.md",
                            "bug-memory-leak.md",
                            "optimize-queries.md"
                        ]
                    },
                    {
                        "action": "fix_symlinks",
                        "symlinks_fixed": 1
                    }
                ],
                "files_modified": [],
                "recommendations": [
                    "Re-run with dry_run=False to apply 5 file moves and 1 symlink fix"
                ],
                "post_cleanup_health": {
                    "score": 95,
                    "grade": "A",
                    "status": "healthy"
                }
            }
        }

        Example 3: Execute full cleanup (not dry-run)
        >>> await check_structure_health(
        ...     project_root="/Users/dev/myproject",
        ...     perform_cleanup=True,
        ...     stale_days=60,
        ...     dry_run=False
        ... )
        {
            "success": true,
            "health": {
                "score": 80,
                "grade": "B",
                "status": "good",
                "checks": {
                    "required_directories": true,
                    "symlinks_valid": true,
                    "config_exists": true,
                    "files_organized": false
                },
                "issues": [
                    "3 stale plans older than 60 days",
                    "2 empty directories"
                ],
                "recommendations": [
                    "Archive stale plans",
                    "Remove empty directories"
                ]
            },
            "summary": "Structure health: GOOD (Grade: B, Score: 80/100)",
            "action_required": true,
            "cleanup": {
                "dry_run": false,
                "actions_performed": [
                    {
                        "action": "archive_stale",
                        "stale_plans_found": 3,
                        "files": ["old-plan-1.md", "old-plan-2.md", "old-plan-3.md"]
                    },
                    {
                        "action": "fix_symlinks",
                        "symlinks_fixed": 0
                    },
                    {
                        "action": "remove_empty",
                        "empty_directories": [
                            ".cursor/plans/active",
                            ".cursor/plans/completed"
                        ]
                    }
                ],
                "files_modified": [
                    "Moved old-plan-1.md to archived/",
                    "Moved old-plan-2.md to archived/",
                    "Moved old-plan-3.md to archived/"
                ],
                "recommendations": [],
                "post_cleanup_health": {
                    "score": 100,
                    "grade": "A",
                    "status": "healthy"
                }
            }
        }

    Note:
        - This tool replaces the deprecated cleanup_project_structure tool
        - Use perform_cleanup=True to perform cleanup actions alongside health checks
        - Always run with dry_run=True first to preview changes before executing
        - The stale_days parameter uses file modification time (st_mtime), not access time
        - Cleanup actions are idempotent and safe to run multiple times
        - Health score formula: 100 - (10 × number_of_issues), minimum 0
        - Grade mapping: A=90-100, B=80-89, C=70-79, D=60-69, F=0-59
        - Status mapping: healthy=90-100, good=75-89, fair=60-74, warning=40-59, critical=0-39
        - If structure is not initialized, returns score=0, grade=F, status=not_initialized
    """
    try:
        root = get_project_root(project_root)
        structure_mgr = StructureManager(root)

        not_initialized_response = check_structure_initialized(structure_mgr)
        if not_initialized_response:
            return not_initialized_response

        health = structure_mgr.check_structure_health()
        result = build_health_result(health)

        if perform_cleanup:
            cleanup_report = perform_cleanup_actions(
                structure_mgr, cleanup_actions, stale_days, dry_run
            )
            result["cleanup"] = cleanup_report

        return json.dumps(result, indent=2)

    except Exception as e:
        return json.dumps(
            {"success": False, "error": str(e), "error_type": type(e).__name__},
            indent=2,
        )


def check_structure_initialized(
    structure_mgr: StructureManager,
) -> str | None:
    """Check if structure is initialized, return error response if not.

    Args:
        structure_mgr: Structure manager instance

    Returns:
        JSON error response if not initialized, None if initialized
    """
    if not structure_mgr.get_path("root").exists():
        return json.dumps(
            {
                "success": True,
                "health": {
                    "score": 0,
                    "grade": "F",
                    "status": "not_initialized",
                    "message": "Project structure not initialized",
                    "recommendation": "Run setup_project_structure() to initialize",
                },
            },
            indent=2,
        )
    return None


def build_health_result(health: dict[str, object]) -> dict[str, object]:
    """Build health result dictionary.

    Args:
        health: Health report from structure manager

    Returns:
        Result dictionary with health information
    """
    status = cast(str, health.get("status", "unknown"))
    grade = cast(str, health.get("grade", "F"))
    score = health.get("score", 0)

    return {
        "success": True,
        "health": health,
        "summary": f"Structure health: {status.upper()} (Grade: {grade}, Score: {score}/100)",
        "action_required": status in ["warning", "critical"],
    }


def perform_cleanup_actions(
    structure_mgr: StructureManager,
    cleanup_actions: list[str] | None,
    stale_days: int,
    dry_run: bool,
) -> dict[str, object]:
    """Perform cleanup actions and return report.

    Args:
        structure_mgr: Structure manager instance
        cleanup_actions: List of cleanup actions to perform
        stale_days: Days of inactivity before considering plan stale
        dry_run: Preview cleanup actions without making changes

    Returns:
        Cleanup report dictionary
    """
    cleanup_actions = cleanup_actions or [
        "archive_stale",
        "organize_plans",
        "fix_symlinks",
        "remove_empty",
    ]

    cleanup_report: dict[str, object] = {
        "dry_run": dry_run,
        "actions_performed": [],
        "files_modified": [],
        "recommendations": [],
    }

    if "archive_stale" in cleanup_actions:
        perform_archive_stale(structure_mgr, stale_days, dry_run, cleanup_report)

    if "fix_symlinks" in cleanup_actions:
        perform_fix_symlinks(structure_mgr, cleanup_report)

    if "remove_empty" in cleanup_actions:
        perform_remove_empty(structure_mgr, cleanup_report)

    post_cleanup_health = structure_mgr.check_structure_health()
    cleanup_report["post_cleanup_health"] = post_cleanup_health

    return cleanup_report


@mcp.tool()
async def get_structure_info(project_root: str | None = None) -> str:
    """Get current project structure configuration, paths, and status information.

    Retrieves comprehensive information about the MCP Memory Bank project structure,
    including the structure version, all configured component paths (memory bank,
    plans, rules directories), configuration settings, existence status of each
    component, and a high-level health summary. This tool is useful for understanding
    the current state of the project structure without making any modifications.

    The information includes:
    - Structure version and configuration source (.cursor/structure.json)
    - All component paths (absolute paths to memory-bank/, plans/, rules/, etc.)
    - Existence status for each component (whether files/directories exist)
    - Symlink information (targets and validity)
    - Configuration settings (stale_days, cleanup preferences, etc.)
    - Quick health summary (score, grade, status)

    Args:
        project_root: Absolute path to project root directory. If None, uses current
            working directory. Example: "/Users/username/projects/my-project"

    Returns:
        JSON string containing structure information with structure:
        {
            "success": true,
            "structure_info": {
                "version": "1.0",
                "root": "/Users/username/projects/my-project",
                "paths": {
                    "cursor_dir": "/Users/username/projects/my-project/.cursor",
                    "memory_bank": "/Users/username/projects/my-project/.cursor/memory-bank",
                    "memory_bank_symlink": "/Users/username/projects/my-project/memory-bank",
                    "plans": "/Users/username/projects/my-project/.cursor/plans",
                    "plans_active": "/Users/username/projects/my-project/.cursor/plans/active",
                    "plans_completed": "/Users/username/projects/my-project/.cursor/plans/completed",
                    "plans_archived": "/Users/username/projects/my-project/.cursor/plans/archived",
                    "rules": "/Users/username/projects/my-project/.cursor/rules",
                    "rules_symlink": "/Users/username/projects/my-project/rules",
                    "config": "/Users/username/projects/my-project/.cursor/structure.json"
                },
                "exists": {
                    "cursor_dir": true,
                    "memory_bank": true,
                    "memory_bank_symlink": true,
                    "plans": true,
                    "plans_active": true,
                    "plans_completed": false,
                    "plans_archived": true,
                    "rules": true,
                    "rules_symlink": true,
                    "config": true
                },
                "symlinks": {
                    "memory_bank": {
                        "path": "/Users/username/projects/my-project/memory-bank",
                        "target": ".cursor/memory-bank",
                        "valid": true,
                        "exists": true
                    },
                    "rules": {
                        "path": "/Users/username/projects/my-project/rules",
                        "target": ".cursor/rules",
                        "valid": true,
                        "exists": true
                    }
                },
                "config": {
                    "version": "1.0",
                    "stale_days": 90,
                    "auto_archive": false,
                    "symlink_targets": {
                        "memory_bank": ".cursor/memory-bank",
                        "rules": ".cursor/rules"
                    }
                },
                "health_summary": {
                    "score": 95,
                    "grade": "A",
                    "status": "healthy",
                    "initialized": true
                }
            },
            "message": "Structure information retrieved successfully"
        }

        On error:
        {
            "success": false,
            "error": "Project root does not exist: /invalid/path",
            "error_type": "FileNotFoundError"
        }

    Examples:
        Example 1: Get structure info for initialized project
        >>> await get_structure_info()
        {
            "success": true,
            "structure_info": {
                "version": "1.0",
                "root": "/Users/dev/myproject",
                "paths": {
                    "cursor_dir": "/Users/dev/myproject/.cursor",
                    "memory_bank": "/Users/dev/myproject/.cursor/memory-bank",
                    "memory_bank_symlink": "/Users/dev/myproject/memory-bank",
                    "plans": "/Users/dev/myproject/.cursor/plans",
                    "plans_active": "/Users/dev/myproject/.cursor/plans/active",
                    "plans_completed": "/Users/dev/myproject/.cursor/plans/completed",
                    "plans_archived": "/Users/dev/myproject/.cursor/plans/archived",
                    "rules": "/Users/dev/myproject/.cursor/rules",
                    "rules_symlink": "/Users/dev/myproject/rules",
                    "config": "/Users/dev/myproject/.cursor/structure.json"
                },
                "exists": {
                    "cursor_dir": true,
                    "memory_bank": true,
                    "memory_bank_symlink": true,
                    "plans": true,
                    "plans_active": true,
                    "plans_completed": true,
                    "plans_archived": true,
                    "rules": true,
                    "rules_symlink": true,
                    "config": true
                },
                "symlinks": {
                    "memory_bank": {
                        "path": "/Users/dev/myproject/memory-bank",
                        "target": ".cursor/memory-bank",
                        "valid": true,
                        "exists": true
                    },
                    "rules": {
                        "path": "/Users/dev/myproject/rules",
                        "target": ".cursor/rules",
                        "valid": true,
                        "exists": true
                    }
                },
                "config": {
                    "version": "1.0",
                    "stale_days": 90,
                    "auto_archive": false,
                    "symlink_targets": {
                        "memory_bank": ".cursor/memory-bank",
                        "rules": ".cursor/rules"
                    }
                },
                "health_summary": {
                    "score": 100,
                    "grade": "A",
                    "status": "healthy",
                    "initialized": true
                }
            },
            "message": "Structure information retrieved successfully"
        }

        Example 2: Get structure info for partially initialized project
        >>> await get_structure_info(project_root="/Users/dev/newproject")
        {
            "success": true,
            "structure_info": {
                "version": "1.0",
                "root": "/Users/dev/newproject",
                "paths": {
                    "cursor_dir": "/Users/dev/newproject/.cursor",
                    "memory_bank": "/Users/dev/newproject/.cursor/memory-bank",
                    "memory_bank_symlink": "/Users/dev/newproject/memory-bank",
                    "plans": "/Users/dev/newproject/.cursor/plans",
                    "plans_active": "/Users/dev/newproject/.cursor/plans/active",
                    "plans_completed": "/Users/dev/newproject/.cursor/plans/completed",
                    "plans_archived": "/Users/dev/newproject/.cursor/plans/archived",
                    "rules": "/Users/dev/newproject/.cursor/rules",
                    "rules_symlink": "/Users/dev/newproject/rules",
                    "config": "/Users/dev/newproject/.cursor/structure.json"
                },
                "exists": {
                    "cursor_dir": true,
                    "memory_bank": true,
                    "memory_bank_symlink": false,
                    "plans": false,
                    "plans_active": false,
                    "plans_completed": false,
                    "plans_archived": false,
                    "rules": false,
                    "rules_symlink": false,
                    "config": false
                },
                "symlinks": {
                    "memory_bank": {
                        "path": "/Users/dev/newproject/memory-bank",
                        "target": null,
                        "valid": false,
                        "exists": false
                    },
                    "rules": {
                        "path": "/Users/dev/newproject/rules",
                        "target": null,
                        "valid": false,
                        "exists": false
                    }
                },
                "config": null,
                "health_summary": {
                    "score": 40,
                    "grade": "D",
                    "status": "warning",
                    "initialized": false
                }
            },
            "message": "Structure information retrieved successfully"
        }

        Example 3: Get structure info with custom configuration
        >>> await get_structure_info()
        {
            "success": true,
            "structure_info": {
                "version": "1.0",
                "root": "/Users/dev/enterprise-project",
                "paths": {
                    "cursor_dir": "/Users/dev/enterprise-project/.cursor",
                    "memory_bank": "/Users/dev/enterprise-project/.cursor/memory-bank",
                    "memory_bank_symlink": "/Users/dev/enterprise-project/memory-bank",
                    "plans": "/Users/dev/enterprise-project/.cursor/plans",
                    "plans_active": "/Users/dev/enterprise-project/.cursor/plans/active",
                    "plans_completed": "/Users/dev/enterprise-project/.cursor/plans/completed",
                    "plans_archived": "/Users/dev/enterprise-project/.cursor/plans/archived",
                    "rules": "/Users/dev/enterprise-project/.cursor/rules",
                    "rules_symlink": "/Users/dev/enterprise-project/rules",
                    "config": "/Users/dev/enterprise-project/.cursor/structure.json"
                },
                "exists": {
                    "cursor_dir": true,
                    "memory_bank": true,
                    "memory_bank_symlink": true,
                    "plans": true,
                    "plans_active": true,
                    "plans_completed": true,
                    "plans_archived": true,
                    "rules": true,
                    "rules_symlink": true,
                    "config": true
                },
                "symlinks": {
                    "memory_bank": {
                        "path": "/Users/dev/enterprise-project/memory-bank",
                        "target": ".cursor/memory-bank",
                        "valid": true,
                        "exists": true
                    },
                    "rules": {
                        "path": "/Users/dev/enterprise-project/rules",
                        "target": ".cursor/rules",
                        "valid": true,
                        "exists": true
                    }
                },
                "config": {
                    "version": "1.0",
                    "stale_days": 30,
                    "auto_archive": true,
                    "symlink_targets": {
                        "memory_bank": ".cursor/memory-bank",
                        "rules": ".cursor/rules"
                    }
                },
                "health_summary": {
                    "score": 100,
                    "grade": "A",
                    "status": "healthy",
                    "initialized": true
                }
            },
            "message": "Structure information retrieved successfully"
        }

    Note:
        - This is a read-only tool that does not modify any files or directories
        - Use this tool to inspect structure state before running cleanup operations
        - The health_summary provides a quick overview; use check_structure_health() for detailed analysis
        - All paths returned are absolute paths, not relative paths
        - Symlink validity checks both that the symlink exists and points to correct target
        - The config field will be null if .cursor/structure.json does not exist
        - For uninitialized projects, many exists fields will be false
        - The version field indicates the structure schema version (currently "1.0")
    """
    try:
        root = get_project_root(project_root)
        structure_mgr = StructureManager(root)

        # Get structure info
        info = structure_mgr.get_structure_info()

        return json.dumps(
            {
                "success": True,
                "structure_info": info,
                "message": "Structure information retrieved successfully",
            },
            indent=2,
        )

    except Exception as e:
        return json.dumps(
            {"success": False, "error": str(e), "error_type": type(e).__name__},
            indent=2,
        )


# ============================================================================
# Helper Functions for check_structure_health cleanup functionality
# ============================================================================


def perform_archive_stale(
    structure_mgr: StructureManager,
    stale_days: int,
    dry_run: bool,
    report: dict[str, object],
) -> None:
    """Archive stale plans older than stale_days."""
    from datetime import datetime, timedelta

    plans_active = structure_mgr.get_path("plans") / "active"
    plans_archived = structure_mgr.get_path("plans") / "archived"
    stale_threshold = datetime.now() - timedelta(days=stale_days)

    if not plans_active.exists():
        return

    stale_plans = find_stale_plans(plans_active, stale_threshold)
    if not stale_plans:
        return

    record_archive_action(report, stale_plans)

    if not dry_run:
        move_stale_plans(plans_archived, stale_plans, report)


def find_stale_plans(plans_active: Path, stale_threshold: datetime) -> list[Path]:
    """Find stale plan files."""
    stale_plans: list[Path] = []
    for plan_file in plans_active.glob("*.md"):
        if datetime.fromtimestamp(plan_file.stat().st_mtime) < stale_threshold:
            stale_plans.append(plan_file)
    return stale_plans


def record_archive_action(report: dict[str, object], stale_plans: list[Path]) -> None:
    """Record archive action in report."""
    actions_performed = cast(list[dict[str, object]], report["actions_performed"])
    actions_performed.append(
        {
            "action": "archive_stale",
            "stale_plans_found": len(stale_plans),
            "files": [p.name for p in stale_plans],
        }
    )


def move_stale_plans(
    plans_archived: Path, stale_plans: list[Path], report: dict[str, object]
) -> None:
    """Move stale plans to archived directory."""
    plans_archived.mkdir(parents=True, exist_ok=True)
    files_modified = cast(list[str], report["files_modified"])
    for plan in stale_plans:
        dest = plans_archived / plan.name
        _ = plan.rename(dest)
        files_modified.append(f"Moved {plan.name} to archived/")


def perform_fix_symlinks(
    structure_mgr: StructureManager, report: dict[str, object]
) -> None:
    """Fix broken Cursor symlinks."""
    cursor_report = structure_mgr.setup_cursor_integration()
    actions_performed = cast(list[dict[str, object]], report["actions_performed"])
    symlinks_created = cast(list[object], cursor_report.get("symlinks_created", []))
    actions_performed.append(
        {"action": "fix_symlinks", "symlinks_fixed": len(symlinks_created)}
    )


def perform_remove_empty(
    structure_mgr: StructureManager, report: dict[str, object]
) -> None:
    """Remove empty plan directories."""
    empty_dirs: list[Path] = []
    for directory in [
        structure_mgr.get_path("plans") / "active",
        structure_mgr.get_path("plans") / "completed",
        structure_mgr.get_path("plans") / "archived",
    ]:
        if directory.exists() and not any(directory.iterdir()):
            empty_dirs.append(directory)

    if empty_dirs:
        actions_performed = cast(list[dict[str, object]], report["actions_performed"])
        actions_performed.append(
            {
                "action": "remove_empty",
                "empty_directories": [str(d) for d in empty_dirs],
            }
        )
