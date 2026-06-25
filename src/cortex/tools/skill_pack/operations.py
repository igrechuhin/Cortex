"""Agent Skill Pack discovery, loading, and execution (plan: agent-skills-and-composability).

Single MCP tool skill_pack(operation="discover"|"load"|"execute") for dynamic skill pack
discovery, loading, and workflow execution. Manifests are read from package resources
(cortex/resources/skills/*.json). Consolidated to keep tool count within
MAX_REGISTERED_TOOLS without raising the limit.
"""

import json
import logging
from collections.abc import Callable
from pathlib import Path
from typing import Literal

from cortex.core.constants import MCP_TOOL_TIMEOUT_FAST
from cortex.core.mcp_stability import ensure_usage_context, mcp_tool_wrapper
from cortex.tools.response_builder import error_response, success_response
from cortex.tools.skill_pack.models import (
    PhaseResult,
    SkillPackManifest,
    SkillWorkflowPhase,
    SkillWorkflowResult,
)

logger = logging.getLogger(__name__)

_skills_dir: Path | None = None


def _get_skills_dir() -> Path:
    """Return the path to the skills manifest directory (package resources)."""
    global _skills_dir
    if _skills_dir is None:
        # cortex/tools/skill_pack/operations.py -> cortex/resources/skills
        _skills_dir = (
            Path(__file__).resolve().parent.parent.parent / "resources" / "skills"
        )
    return _skills_dir


def _load_all_manifests() -> list[SkillPackManifest]:
    """Load all skill pack manifests from the skills directory."""
    skills_dir = _get_skills_dir()
    if not skills_dir.is_dir():
        return []
    manifests: list[SkillPackManifest] = []
    for path in sorted(skills_dir.glob("*.json")):
        try:
            raw = path.read_text(encoding="utf-8")
            manifest = SkillPackManifest.model_validate_json(raw)
            manifests.append(manifest)
        except (OSError, ValueError) as e:
            logger.debug("_load_all_manifests: skip %s: %s", path.name, e)
            continue
    return manifests


def _score_pack_for_task(manifest: SkillPackManifest, task_description: str) -> int:
    """Score a pack's relevance to task_description (higher = more relevant)."""
    if not task_description or not task_description.strip():
        return 0
    task_lower = task_description.lower().strip()
    score = 0
    if manifest.description and manifest.description.lower() in task_lower:
        score += 2
    for kw in manifest.keywords:
        if kw.lower() in task_lower:
            score += 1
    if manifest.when_to_use and any(
        w in task_lower for w in manifest.when_to_use.lower().split()
    ):
        score += 1
    return score


def _skill_pack_discover_result(task_description: str | None, limit: int) -> str:
    """Validate and run discover; return JSON string."""
    desc = (task_description or "").strip()
    if not desc:
        return json.dumps(
            error_response(
                error="task_description required when operation is discover",
            ),
            indent=2,
        )
    return _do_discover(desc, limit)


def _skill_pack_load_result(pack_name: str | None) -> str:
    """Validate and run load; return JSON string."""
    name = (pack_name or "").strip()
    if not name:
        return json.dumps(
            error_response(
                error="pack_name required when operation is load",
            ),
            indent=2,
        )
    return _do_load(name)


def _do_discover(task_description: str, limit: int = 5) -> str:
    """Recommend skill packs relevant to a task description. Internal helper."""
    if limit < 1:
        limit = 1
    if limit > 10:
        limit = 10
    manifests = _load_all_manifests()
    scored: list[tuple[int, SkillPackManifest]] = [
        (_score_pack_for_task(m, task_description), m) for m in manifests
    ]
    scored.sort(key=lambda x: (-x[0], x[1].name))
    recommended = [s[1] for s in scored if s[0] > 0][:limit]
    if not recommended and manifests:
        recommended = [scored[0][1]] if scored else []
    result = success_response(
        task_description=task_description,
        count=len(recommended),
        packs=[
            {
                "name": m.name,
                "description": m.description,
                "reason": (
                    "Keywords or description match"
                    if _score_pack_for_task(m, task_description) > 0
                    else "Default recommendation"
                ),
            }
            for m in recommended
        ],
    )
    return json.dumps(result, indent=2)


def _build_tool_registry() -> dict[str, Callable[..., object]]:
    """Return a name→callable map for tools usable in skill workflows.

    # AI: Deferred import to avoid circular dependencies; registry is built
    # lazily on first execute call, not at module load time.
    # plan is included so planning.json workflow phases can call it.
    """
    from cortex.tools.execution.pre_commit_zero_arg_tools import (  # noqa: PLC0415
        autofix,
        run_quality_gate,
    )
    from cortex.tools.files.crud_operations import manage_file  # noqa: PLC0415
    from cortex.tools.plans.plan import plan  # noqa: PLC0415
    from cortex.tools.session.sequential_thinking import think  # noqa: PLC0415

    # AI: think and manage_file added for refactoring workflow analyse/apply phases.
    return {
        "run_quality_gate": run_quality_gate,
        "autofix": autofix,
        "plan": plan,
        "think": think,
        "manage_file": manage_file,
    }


# AI: Populated lazily on first execute call so module-level import stays clean.
# Lowercase name avoids pyright reportConstantRedefinition on global reassignment.
_tool_registry: dict[str, Callable[..., object]] | None = None


def _get_tool_registry() -> dict[str, Callable[..., object]]:
    """Return the shared tool registry, building it on first access."""
    global _tool_registry  # noqa: PLW0603
    if _tool_registry is None:
        _tool_registry = _build_tool_registry()
    return _tool_registry


def _eval_condition(expr: str, ctx: dict[str, object]) -> bool:
    """Evaluate a condition expression string against ctx. Returns True on error."""
    try:
        result = eval(expr, {"__builtins__": {}}, ctx)  # noqa: S307
        return bool(result)
    except Exception:
        logger.debug("_eval_condition: failed to evaluate %r", expr)
        return True


def resolve_workflow_inputs(
    phase: SkillWorkflowPhase,
    ctx: dict[str, object],
    phase_inputs: dict[str, dict[str, object]],
) -> dict[str, object]:
    """Build kwargs for the tool call by resolving phase.inputs and caller phase_inputs.

    # AI: Inputs map uses 'prior_phase.field' keys to thread outputs between phases.
    # phase_inputs[phase.name] supplies caller-provided initial values (e.g. plan_title).
    # Resolved prior-phase values are merged over caller values so data-passing always
    # reflects actual tool output rather than stale caller input.
    """
    kwargs: dict[str, object] = dict(phase_inputs.get(phase.name, {}))
    for src_key, param_name in phase.inputs.items():
        # src_key format: "prior_phase_name.field_name"
        parts = src_key.split(".", 1)
        if len(parts) != 2:
            continue
        prior_phase_name, field_name = parts
        prior_ctx = ctx.get(prior_phase_name)
        if isinstance(prior_ctx, dict) and field_name in prior_ctx:
            kwargs[param_name] = prior_ctx[field_name]
    return kwargs


def _call_tool(
    tool_fn: Callable[..., object], kwargs: dict[str, object] | None = None
) -> dict[str, object]:
    """Call a tool function (sync or async coroutine) and return parsed JSON dict."""
    import asyncio  # noqa: PLC0415
    import inspect  # noqa: PLC0415

    kw = kwargs or {}
    if inspect.iscoroutinefunction(tool_fn):
        result = asyncio.run(tool_fn(**kw))
    else:
        result = tool_fn(**kw)
    if isinstance(result, str):
        try:
            parsed: dict[str, object] = json.loads(result)
            return parsed
        except json.JSONDecodeError:
            return {"status": "error", "error": result}
    if isinstance(result, dict):
        return result  # type: ignore[return-value]
    return {"status": "error", "error": f"Unexpected tool result type: {type(result)}"}


def _run_phase_iteration(
    tool_fn: Callable[..., object],
    phase: SkillWorkflowPhase,
    ctx: dict[str, object],
    kwargs: dict[str, object],
) -> tuple[bool, dict[str, object]]:
    """Run one iteration of a phase tool call. Returns (passed, captured_outputs)."""
    raw = _call_tool(tool_fn, kwargs)
    captured = {k: raw.get(k) for k in phase.outputs if k in raw}
    if phase.success_condition:
        passed = _eval_condition(phase.success_condition, dict(raw))
    else:
        passed = raw.get("status") != "error"
    # AI: Store phase outputs in ctx so later phases and retry_condition can read them.
    ctx[phase.name] = dict(raw)
    return passed, captured


def _run_phase_retry_loop(
    tool_fn: Callable[..., object],
    phase: SkillWorkflowPhase,
    ctx: dict[str, object],
    kwargs: dict[str, object],
) -> tuple[int, bool, dict[str, object]]:
    """Run phase tool up to max_iterations; return (iterations, passed, outputs)."""
    iterations, passed, last_outputs = 0, False, {}
    for _ in range(phase.max_iterations):
        iterations += 1
        passed, last_outputs = _run_phase_iteration(tool_fn, phase, ctx, kwargs)
        if phase.retry_condition and not _eval_condition(phase.retry_condition, ctx):
            break
        if not phase.retry_condition:
            break
    return iterations, passed, last_outputs


def _build_phase_kwargs(
    phase: SkillWorkflowPhase,
    ctx: dict[str, object],
    phase_inputs: dict[str, dict[str, object]],
) -> dict[str, object]:
    """Build tool call kwargs: resolve inputs then inject operation if set."""
    kwargs = resolve_workflow_inputs(phase, ctx, phase_inputs)
    # AI: Inject phase.operation into kwargs so tools like plan() receive the correct operation.
    if phase.operation is not None and "operation" not in kwargs:
        kwargs["operation"] = phase.operation
    return kwargs


def _execute_one_phase(
    phase: SkillWorkflowPhase,
    ctx: dict[str, object],
    handoff_fn: Callable[[str, str, dict[str, object]], None],
    pack_name: str,
    phase_inputs: dict[str, dict[str, object]],
) -> PhaseResult:
    """Execute a single workflow phase with retry logic. Returns PhaseResult."""
    if phase.condition and not _eval_condition(phase.condition, ctx):
        skipped = PhaseResult(name=phase.name, iterations=0, passed=True, skipped=True)
        handoff_fn(pack_name, phase.name, skipped.model_dump(mode="json"))
        return skipped
    registry = _get_tool_registry()
    if phase.tool not in registry:
        err = PhaseResult(
            name=phase.name,
            iterations=0,
            passed=False,
            error=f"Tool not in registry: {phase.tool}",
        )
        handoff_fn(pack_name, phase.name, err.model_dump(mode="json"))
        return err
    kwargs = _build_phase_kwargs(phase, ctx, phase_inputs)
    iters, passed, outputs = _run_phase_retry_loop(
        registry[phase.tool], phase, ctx, kwargs
    )
    result = PhaseResult(
        name=phase.name, iterations=iters, passed=passed, outputs=outputs
    )
    handoff_fn(pack_name, phase.name, result.model_dump(mode="json"))
    return result


def _noop_handoff(pack_name: str, phase_name: str, data: dict[str, object]) -> None:
    """No-op pipeline_handoff stub used when handoff is not injected."""


def _workflow_all_passed(
    phase_results: list[PhaseResult], workflow_phases: list[SkillWorkflowPhase]
) -> bool:
    """Return True when the last required non-skipped phase passed."""
    # AI: Final passed is determined by the last required phase that ran (not skipped).
    # Earlier required phases may fail and trigger recovery phases; the last required
    # phase reflects the codebase's final quality state.
    required = [
        pr
        for pr, p in zip(phase_results, workflow_phases)
        if p.required and not pr.skipped
    ]
    return required[-1].passed if required else True


def execute_sequential_workflow(
    manifest: SkillPackManifest,
    handoff_fn: Callable[[str, str, dict[str, object]], None] | None = None,
    phase_inputs: dict[str, dict[str, object]] | None = None,
) -> SkillWorkflowResult:
    """Run a sequential skill workflow phase-by-phase and return a structured result.

    # AI: handoff_fn is injected so unit tests can pass a no-op stub without
    # touching the real pipeline_handoff MCP tool.
    # phase_inputs maps phase name → initial kwargs for that phase (e.g. plan_title for create).
    """
    if manifest.workflow is None:
        return SkillWorkflowResult(
            passed=False,
            iterations=0,
            phases=[],
            error=f"Skill pack '{manifest.name}' has no workflow block",
        )
    handoff = handoff_fn if handoff_fn is not None else _noop_handoff
    pi: dict[str, dict[str, object]] = phase_inputs or {}
    ctx: dict[str, object] = {}
    phase_results: list[PhaseResult] = []
    total_iterations = 0
    for phase in manifest.workflow.phases:
        pr = _execute_one_phase(phase, ctx, handoff, manifest.name, pi)
        phase_results.append(pr)
        total_iterations += pr.iterations
    return SkillWorkflowResult(
        passed=_workflow_all_passed(phase_results, manifest.workflow.phases),
        iterations=total_iterations,
        phases=phase_results,
    )


def _find_manifest(name: str) -> tuple[SkillPackManifest | None, list[str]]:
    """Return (manifest, available_names) for the given pack name."""
    manifests = _load_all_manifests()
    match = next((m for m in manifests if m.name.lower() == name.lower()), None)
    return match, [m.name for m in manifests]


def _skill_pack_execute_result(
    pack_name: str | None,
    phase_inputs: dict[str, dict[str, object]] | None = None,
) -> str:
    """Validate and run execute; return JSON string."""
    name = (pack_name or "").strip()
    if not name:
        return json.dumps(
            error_response(error="pack_name required when operation is execute"),
            indent=2,
        )
    manifest, available = _find_manifest(name)
    if manifest is None:
        return json.dumps(
            error_response(
                error=f"Skill pack not found: {pack_name}",
                available=[str(n) for n in available],
            ),
            indent=2,
        )
    if manifest.workflow is None:
        return json.dumps(
            error_response(error=f"Skill pack '{pack_name}' has no workflow block"),
            indent=2,
        )
    wf_result = execute_sequential_workflow(manifest, phase_inputs=phase_inputs)
    return json.dumps(
        success_response(**wf_result.model_dump(mode="json")),
        indent=2,
    )


def _do_load(pack_name: str) -> str:
    """Load a skill pack by name. Internal helper."""
    manifests = _load_all_manifests()
    name_lower = pack_name.strip().lower()
    for m in manifests:
        if m.name.lower() == name_lower:
            return json.dumps(
                success_response(pack=m.model_dump(mode="json")),
                indent=2,
            )
    return json.dumps(
        error_response(
            error=f"Skill pack not found: {pack_name}",
            available=[m.name for m in manifests],
        ),
        indent=2,
    )


# Internalized for tool budget reduction (2026-02-26). Kept as callable for tests and internal use.
@ensure_usage_context
@mcp_tool_wrapper(timeout=MCP_TOOL_TIMEOUT_FAST)
async def skill_pack(
    operation: Literal["discover", "load", "execute"],
    task_description: str | None = None,
    pack_name: str | None = None,
    limit: int = 5,
    phase_inputs: dict[str, dict[str, object]] | None = None,
) -> str:
    """Discover skill packs for a task or load a pack by name.

    USE WHEN: For \"discover\" — agent wants to know which skill packs are
    relevant for the current task. For \"load\" — agent wants full guidance
    for a pack (tools, workflows, examples, troubleshooting).

    EXAMPLES: skill_pack(operation=\"discover\", task_description=\"implement feature\"),
    skill_pack(operation=\"load\", pack_name=\"core\").

    RETURNS: For discover — JSON with status, count, and recommended packs.
    For load — JSON with status and full manifest or error.

    Args:
        operation: \"discover\" or \"load\".
        task_description: Required for discover. Natural language task to match
            against pack keywords and descriptions.
        pack_name: Required for load. Pack name (e.g. \"core\", \"quality\").
            Case-insensitive.
        limit: Max packs to return for discover (1–10, default 5).

    Example (discover):
        >>> await skill_pack(operation="discover", task_description="implement feature", limit=3)
        {
          "status": OperationStatus.SUCCESS.value,
          "operation": "discover",
          "count": 2,
          "packs": [
            {"name": "core", "relevance": 0.92, "description": "Core implementation workflows"},
            {"name": "quality", "relevance": 0.75, "description": "Code quality and pre-commit"}
          ]
        }

    Example (load):
        >>> await skill_pack(operation="load", pack_name="core")
        {
          "status": OperationStatus.SUCCESS.value,
          "operation": "load",
          "pack_name": "core",
          "manifest": {"tools": [...], "workflows": [...], "examples": [...]}
        }

    Example (error — unknown operation):
        >>> await skill_pack(operation="other")
        {"status": OperationStatus.ERROR.value, "error": "Unknown operation: 'other'. Use discover or load."}
    """
    op = (operation or "").strip().lower()
    if op == "discover":
        return _skill_pack_discover_result(task_description, limit)
    if op == "load":
        return _skill_pack_load_result(pack_name)
    if op == "execute":
        return _skill_pack_execute_result(pack_name, phase_inputs=phase_inputs)
    return json.dumps(
        error_response(
            error=f"Unknown operation: {operation!r}. Use discover, load, or execute.",
        ),
        indent=2,
    )
