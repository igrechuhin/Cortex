"""Helper functions for script capture tools (payload building, summaries)."""

from cortex.core.models import OperationStatus
from cortex.script_analysis.models import ScriptAnalysisResult
from cortex.script_detection.models import ScriptCaptureRecord
from cortex.script_promotion.models import ValidationResult
from cortex.script_promotion.script_integrator import script_integration_template
from cortex.script_promotion.tool_converter import tool_conversion_template


def record_to_summary(record: ScriptCaptureRecord) -> dict[str, object]:
    """Build a JSON-serializable summary from a ScriptCaptureRecord."""
    return {
        "script_id": record.script_id,
        "timestamp": record.timestamp,
        "task_description": record.task_description,
        "script_path": record.script_path,
        "script_type": record.script_type,
        "purpose": record.purpose,
        "promotion_status": record.promotion_status.value,
    }


def build_promote_payload(
    record: ScriptCaptureRecord,
    script_id: str,
    validation: ValidationResult,
    output_type: str,
) -> dict[str, object]:
    """Build JSON payload for promote_session_script success response."""
    payload: dict[str, object] = {
        "status": OperationStatus.SUCCESS.value,
        "script_id": script_id,
        "validation_passed": validation.passed,
        "quality_score": validation.quality_score,
        "issues": validation.issues,
    }
    if output_type == "script":
        rel_path, content = script_integration_template(record)
        payload["template_path"] = rel_path
        payload["template_content"] = content
    else:
        payload["template_content"] = tool_conversion_template(record)
    return payload


def analysis_to_summary(obj: ScriptAnalysisResult) -> dict[str, object]:
    """Build JSON-serializable summary from ScriptAnalysisResult."""
    return {
        "script_id": obj.script_id,
        "use_case_label": obj.use_case.use_case_label,
        "keywords": obj.use_case.keywords,
        "gap_reason": obj.gap.gap_reason,
        "is_gap": obj.gap.is_gap,
        "reusability_score": obj.reusability_score,
        "promotion_potential": obj.promotion_potential,
    }
