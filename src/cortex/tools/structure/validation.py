# Copyright (c) 2025 Cortex and contributors. All rights reserved.
# SPDX-License-Identifier: MIT

"""Phase 8 structure validation helpers for health checks."""

import json

from cortex.core.models import JsonDict, ModelDict
from cortex.structure.manager import StructureManager
from cortex.structure.models import HealthCheckResult, HealthResult


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


def build_health_result(health: HealthCheckResult | ModelDict) -> HealthResult:
    """Build health result dictionary.

    Args:
        health: Health report from structure manager

    Returns:
        Result dictionary with health information
    """
    if isinstance(health, dict):
        score_raw = health.get("score", 0)
        score = score_raw if isinstance(score_raw, int) else 0
        grade = str(health.get("grade", "F"))
        status = str(health.get("status", "unknown"))
        return HealthResult(
            success=True,
            health=JsonDict.from_dict(health),
            summary=(
                f"Structure health: {status.upper()} "
                f"(Grade: {grade}, Score: {score}/100)"
            ),
            action_required=status in ["warning", "critical"],
        )

    return HealthResult(
        success=True,
        health=JsonDict.model_validate(health.model_dump()),
        summary=(
            f"Structure health: {health.status.upper()} "
            f"(Grade: {health.grade}, Score: {health.score}/100)"
        ),
        action_required=health.status in ["warning", "critical"],
    )
