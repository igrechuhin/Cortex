"""Real MCP calls and bounded project fixtures shared by workflow tests."""

import importlib
import json
import shutil
import textwrap
from pathlib import Path
from typing import cast

from fastmcp import Client
from mcp.types import Implementation, TextContent

from cortex.server import mcp
from tests.helpers.path_helpers import ensure_test_cortex_structure


def write_memory_bank(root: Path) -> Path:
    memory = ensure_test_cortex_structure(root)
    contents = {
        "activeContext.md": "# Active Context\n\n## Current Focus\n\nPython smoke.\n\n## Next Steps\n\n- Verify workflow.\n",
        "roadmap.md": "# Roadmap\n\n## Pending plans\n",
        "progress.md": "# Progress\n\n## What Works\n\n- Decision: Preserve public workflow isolation.\n\n## What's Left\n\n- Verify workflow.\n",
        "projectBrief.md": "# Project Brief\n\nPython public workflow smoke.\n",
        "systemPatterns.md": "# System Patterns\n\nPython modules.\n",
        "techContext.md": "# Tech Context\n\nPython.\n",
        "productContext.md": "# Product Context\n\nReliable public workflows.\n",
    }
    for name, content in contents.items():
        _ = (memory / name).write_text(content, encoding="utf-8")
    return memory


async def call_public_tool(name: str, **arguments: object) -> dict[str, object]:
    _ = importlib.import_module("cortex.tools")
    identity = Implementation(name="cortex-workflow-smoke", version="1")
    async with Client(mcp, timeout=180, client_info=identity) as client:
        result = await client.call_tool(name, arguments)
    texts = [item.text for item in result.content if isinstance(item, TextContent)]
    assert texts, f"{name} returned no text payload"
    payload = json.loads("".join(texts))
    assert isinstance(payload, dict), payload
    return cast(dict[str, object], payload)


def _prepare_quality_environment(root: Path, environment: Path) -> None:
    (root / ".venv").symlink_to(environment, target_is_directory=True)
    for rule in (root / ".cortex").rglob("*.mdc"):
        content = textwrap.fill(rule.read_text(encoding="utf-8").strip(), width=72)
        _ = rule.write_text("# Rules\n\n" + content + "\n", encoding="utf-8")
    _ = shutil.copytree(
        Path(__file__).resolve().parents[2] / ".cortex" / "synapse" / "scripts",
        root / ".cortex" / "synapse" / "scripts",
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
    )


def write_quality_project(root: Path, environment: Path) -> None:
    """Run real adapter commands against one importable module and one test."""
    _prepare_quality_environment(root, environment)
    source = root / "src" / "cortex"
    source.mkdir(parents=True)
    tests = root / "tests"
    tests.mkdir()
    _ = (source / "smoke_subject.py").write_text(
        "def answer() -> int:\n    return 42\n", encoding="utf-8"
    )
    _ = (tests / "test_subject.py").write_text(
        "from smoke_subject import answer\n\n\ndef test_answer() -> None:\n    assert answer() == 42\n",
        encoding="utf-8",
    )
    _ = (root / "pyproject.toml").write_text(
        '[project]\nname = "public-workflow-smoke"\nversion = "0.0.0"\nrequires-python = ">=3.13"\n'
        + '[tool.pytest.ini_options]\npythonpath = ["src/cortex"]\n'
        + '[tool.pyright]\nextraPaths = ["src/cortex"]\n',
        encoding="utf-8",
    )
    config = root / ".cortex" / ".session" / "publicsmoke01" / "commit"
    config.mkdir(parents=True, exist_ok=True)
    _ = (config / "checks-task.json").write_text(
        json.dumps(
            {"test_timeout": 60, "coverage_threshold": 0.0, "force_fresh": True}
        ),
        encoding="utf-8",
    )
