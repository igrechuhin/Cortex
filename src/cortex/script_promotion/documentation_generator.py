"""Generate documentation for promoted tools and scripts."""


def generate_tool_doc(
    tool_name: str,
    description: str,
    use_case_label: str = "",
    example_args: str = "project_root (optional)",
) -> str:
    """Generate markdown documentation for an MCP tool.

    Args:
        tool_name: Name of the MCP tool.
        description: Short description of what the tool does.
        use_case_label: Optional use case label (e.g. from analysis).
        example_args: Optional example arguments string.

    Returns:
        Markdown string for the tool doc.
    """
    parts = [f"## {tool_name}\n", f"{description}\n"]
    if use_case_label:
        parts.append(f"**Use case**: {use_case_label}\n")
    parts.append(f"**Example**: `{tool_name}({example_args})`\n")
    return "\n".join(parts)


def generate_script_doc(
    script_path: str,
    description: str,
    language: str = "python",
    use_case_label: str = "",
) -> str:
    """Generate markdown documentation for a Synapse script.

    Args:
        script_path: Relative path (e.g. scripts/python/check_foo.py).
        description: Short description of what the script does.
        language: Language directory name.
        use_case_label: Optional use case label.

    Returns:
        Markdown string for the script doc.
    """
    parts = [f"## {script_path}\n", f"{description}\n"]
    if use_case_label:
        parts.append(f"**Use case**: {use_case_label}\n")
    run_cmd = f".venv/bin/python .cortex/synapse/{script_path}"
    parts.append(f"**Run**: `{run_cmd}`\n")
    return "\n".join(parts)
