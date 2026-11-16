"""Cache-independent argv for the approved installed Markdown tool."""

from pathlib import Path

from cortex.tools.execution.pre_commit_markdown_tool import resolve_approved_rumdl


def resolve_rumdl_path(project_root: str | Path | None = None) -> str:
    """Resolve only the reviewed installed package tool; no PATH or manager fallback."""
    root = Path(project_root) if project_root is not None else None
    return str(resolve_approved_rumdl(root))


def markdown_rumdl_argv(root: Path, *, with_fix: bool) -> list[str]:
    """Preserve check/fix flags and configuration without accessing a shared cache."""
    rumdl_config = root / ".rumdl.toml"
    config_args = ["--config", str(rumdl_config)] if rumdl_config.is_file() else []
    fix_args = ["--fix"] if with_fix else []
    return [resolve_rumdl_path(root), "check", *fix_args, *config_args]
