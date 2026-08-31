"""session(operation='predict'): open falsifiable claims for the session.

A prediction is parsed and rejected *before* any edit happens, so a malformed
claim costs a tool call rather than a wasted implementation batch. The claims
are graded automatically by the next ``run_quality_gate()``.
"""

from __future__ import annotations

import json
from pathlib import Path

from cortex.core.context_logging import MCPContext
from cortex.core.models import OperationStatus
from cortex.experience.claims import CLAIM_HELP, ClaimSyntaxError, parse_claims
from cortex.experience.predictions import open_predictions, record_prediction

__all__ = ["session_predict"]


async def _project_root(ctx: MCPContext | None) -> Path:
    from cortex.core.usage_context import (
        get_current_project_root,
        get_or_resolve_project_root,
    )

    return get_current_project_root() or Path(await get_or_resolve_project_root(ctx))


async def session_predict(
    prediction: str | None,
    because: str | None,
    ctx: MCPContext | None = None,
) -> str:
    """Parse, record, and echo back the claims opened for this session."""
    try:
        claims = parse_claims(prediction)
    except ClaimSyntaxError as exc:
        return json.dumps(
            {
                "status": OperationStatus.ERROR.value,
                "error": str(exc),
                "help": CLAIM_HELP,
            },
            indent=2,
        )
    root = await _project_root(ctx)
    from cortex.tools.session.pipeline_handoff_io import get_session_id

    session_id = get_session_id(root)
    node_id = record_prediction(root, session_id, claims, because)
    return json.dumps(
        {
            "status": OperationStatus.SUCCESS.value,
            "recorded": node_id is not None,
            "claims": [claim.model_dump(mode="json") for claim in claims],
            "because": because,
            "open_claims": len(open_predictions(root, session_id)),
            "graded_by": "the next run_quality_gate() call",
        },
        indent=2,
    )
