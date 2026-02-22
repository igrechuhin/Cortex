"""Capture session-generated scripts with metadata."""

from pathlib import Path

from cortex.script_detection.models import (
    PromotionStatus,
    ScriptCaptureRecord,
    make_timestamp_utc,
)
from cortex.script_detection.storage import (
    generate_script_id,
    save_capture,
)


async def capture_script(
    project_root: Path,
    script_path: str,
    script_content: str,
    task_description: str,
    script_type: str = "python",
    purpose: str = "utility",
    usage_context: str | None = None,
    agent_session: str | None = None,
    dependencies: list[str] | None = None,
) -> ScriptCaptureRecord:
    """Capture a session-generated script with metadata.

    Args:
        project_root: Project root (used to resolve .cortex/script-capture).
        script_path: Path to the script (relative or absolute).
        script_content: Full script content.
        task_description: Description of the task that required the script.
        script_type: Language (python, shell, javascript, etc.).
        purpose: Category (utility, analysis, transformation, etc.).
        usage_context: Optional when/why the script was created.
        agent_session: Optional session identifier.
        dependencies: Optional list of dependencies.

    Returns:
        The created ScriptCaptureRecord (with script_id and timestamp).
    """
    script_id = generate_script_id()
    record = ScriptCaptureRecord(
        script_id=script_id,
        timestamp=make_timestamp_utc(),
        task_description=task_description,
        script_path=script_path,
        script_content=script_content,
        script_type=script_type,
        purpose=purpose,
        usage_context=usage_context,
        promotion_status=PromotionStatus.PENDING,
        agent_session=agent_session,
        dependencies=dependencies or [],
    )
    await save_capture(project_root, record)
    return record
