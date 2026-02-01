"""Script detection and capture for session-generated scripts.

This module supports Phase 27: capturing agent-generated scripts during
sessions for analysis and potential promotion to permanent tools/scripts.
"""

from cortex.script_detection.models import ScriptCaptureRecord
from cortex.script_detection.script_capture import capture_script
from cortex.script_detection.storage import ScriptCaptureStore

__all__ = [
    "ScriptCaptureRecord",
    "ScriptCaptureStore",
    "capture_script",
]
