"""Shared metric helpers for optimization strategies."""


def get_excluded_files(
    files_content: dict[str, str],
    selected_files: list[str],
    selected_sections: dict[str, list[str]],
) -> list[str]:
    """Get list of excluded files.

    Args:
        files_content: All file contents
        selected_files: Selected files
        selected_sections: Selected sections

    Returns:
        List of excluded files
    """
    return [
        file_name
        for file_name in files_content
        if file_name not in selected_files and file_name not in selected_sections
    ]
