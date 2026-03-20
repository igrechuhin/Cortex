import pathlib


def _read(path: pathlib.Path) -> str:
    return path.read_text(encoding="utf-8")


def test_readme_mentions_canonical_commands() -> None:
    root = pathlib.Path(__file__).resolve().parents[2]
    readme = _read(root / "README.md")

    assert "bash scripts/bootstrap.sh" in readme
    assert "make check" in readme
    assert "make fix" in readme
    assert "make check-ci-parity" in readme
    assert "make test" in readme


def test_agents_describes_make_check_and_uv_sync_variant() -> None:
    root = pathlib.Path(__file__).resolve().parents[2]
    agents = _read(root / "AGENTS.md")

    assert "make check" in agents
    # All documented uv sync usage should use the canonical form.
    assert "uv sync --extra dev" in agents
    assert "uv sync" in agents


def test_uv_sync_variants_are_canonical() -> None:
    root = pathlib.Path(__file__).resolve().parents[2]
    contents: list[str] = []
    for relative in ["AGENTS.md", "README.md"]:
        contents.append(_read(root / relative))

    joined = "\n".join(contents)
    # If uv sync is referenced at all, it must be the canonical variant.
    if "uv sync" in joined:
        assert "uv sync --extra dev" in joined


def test_mcp_unavailable_read_only_fallback_docs_wired() -> None:
    """AGENTS policy, troubleshooting runbook, and README cross-link stay in sync."""
    root = pathlib.Path(__file__).resolve().parents[2]
    agents = _read(root / "AGENTS.md")
    readme = _read(root / "README.md")
    troubleshooting = _read(root / "docs" / "guides" / "troubleshooting.md")

    assert "### MCP unavailable: read-only audit fallback" in agents
    assert "docs/guides/troubleshooting.md#mcp-unavailable-read-only-audits" in agents
    assert "{#mcp-unavailable-read-only-audits}" in troubleshooting
    assert "MCP unavailable: read-only audits" in troubleshooting
    assert "docs/guides/troubleshooting.md#mcp-unavailable-read-only-audits" in readme
