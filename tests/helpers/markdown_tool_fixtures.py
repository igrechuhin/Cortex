"""Small installed-tool provenance fixtures; fake executables are never launched."""

import base64
import hashlib
import os
from pathlib import Path

from pydantic import BaseModel

from cortex.tools.execution.pre_commit_markdown_tool import APPROVED_RUMDL_VERSION


class MarkdownToolFixture(BaseModel):
    environment: Path
    executable: Path
    metadata: Path
    record: Path


def installed_markdown_tool(root: Path) -> MarkdownToolFixture:
    environment = root / ".venv"
    executable = environment / "bin" / "rumdl"
    executable.parent.mkdir(parents=True)
    content = b"Synthetic recorded executable; do not execute.\n"
    _ = executable.write_bytes(content)
    executable.chmod(0o755)
    metadata = (
        environment
        / "lib"
        / "python3.13"
        / "site-packages"
        / f"rumdl-{APPROVED_RUMDL_VERSION}.dist-info"
    )
    metadata.mkdir(parents=True)
    _ = (metadata / "METADATA").write_text(
        f"Metadata-Version: 2.4\nName: rumdl\nVersion: {APPROVED_RUMDL_VERSION}\n"
    )
    digest = (
        base64.urlsafe_b64encode(hashlib.sha256(content).digest()).decode().rstrip("=")
    )
    record = metadata / "RECORD"
    relative = os.path.relpath(executable, metadata.parent)
    _ = record.write_text(f"{relative},sha256={digest},{len(content)}\n")
    return MarkdownToolFixture(
        environment=environment.resolve(),
        executable=executable.resolve(),
        metadata=metadata,
        record=record,
    )
