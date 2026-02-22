"""
Plan Operations Tools

This module re-exports MCP tools for structured plan creation and roadmap registration.
Implementation is split across:
- plan_crud: create_plan, list_plans, get_plan
- plan_roadmap: register_plan_in_roadmap
- plan_archive: archive path helpers (used by plan_crud)

Tools:
- create_plan: Create a new plan file in the plans directory
- register_plan_in_roadmap: Register a plan in roadmap.md with structured merging
- list_plans: List plan filenames (and optional titles) in the plans directory
- get_plan: Read plan content or metadata by slug

Consumers should import from this module for backward compatibility.
Tests that patch resolve_project_root_async should patch the implementation module
(cortex.tools.plan_crud or cortex.tools.plan_roadmap).
"""

from cortex.tools.plan_crud import (
    CreatePlanResult,
    GetPlanResult,
    ListPlansResult,
    PlanEntry,
    create_plan,
    get_plan,
    list_plans,
)
from cortex.tools.plan_roadmap import (
    RegisterPlanResult,
    register_plan_in_roadmap,
)

__all__ = [
    "CreatePlanResult",
    "GetPlanResult",
    "ListPlansResult",
    "PlanEntry",
    "RegisterPlanResult",
    "create_plan",
    "get_plan",
    "list_plans",
    "register_plan_in_roadmap",
]
