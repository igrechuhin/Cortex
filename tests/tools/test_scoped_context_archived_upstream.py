"""Scoped context includes uniquely resolved archived DONE dependencies."""

from pathlib import Path
from typing import cast

from cortex.core.path_resolver import CortexResourceType, get_cortex_path
from cortex.tools.context.scoped_context import build_scoped_context_packet


def _write_plan(path: Path, status: str, dependencies: str, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    _ = path.write_text(
        "".join(
            (
                f"---\ntitle: {path.stem}\nstatus: {status}\n",
                f"depends_on: [{dependencies}]\n---\n\n{body}\n",
            )
        ),
        encoding="utf-8",
    )


def test_scoped_context_loads_archived_upstream_content(tmp_path: Path) -> None:
    # Arrange
    plans = get_cortex_path(tmp_path, CortexResourceType.PLANS)
    _write_plan(
        plans / "archive" / "Other" / "base.md",
        "DONE",
        "",
        "Archived implementation contract.",
    )
    _write_plan(plans / "leaf.md", "PENDING", '"base"', "Current work.")

    # Act
    packet = build_scoped_context_packet(
        project_root=tmp_path, scope="plan:leaf", rules_payload=""
    )

    # Assert
    assert packet is not None
    upstream = cast(list[dict[str, str]], packet["upstream_plans"])
    assert [row["slug"] for row in upstream] == ["base"]
    assert "Archived implementation contract" in upstream[0]["content"]
