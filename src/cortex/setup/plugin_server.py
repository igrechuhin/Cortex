"""Start the existing MCP server in the workspace selected by the plugin host."""

from pathlib import Path

from cortex.core.usage_context import set_current_project_root


def main() -> None:
    # Bind before importing server registrations: installed scripts are not workspaces.
    set_current_project_root(Path.cwd().resolve())
    from cortex.main import main as run_server

    run_server()


if __name__ == "__main__":
    main()
