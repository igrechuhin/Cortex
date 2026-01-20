"""
Strategy selection logic and file selection helpers.

This module contains helper functions for selecting files and sections
based on relevance scores, mandatory files, and token budgets.
"""

from collections.abc import Callable

from cortex.core.token_counter import TokenCounter


def add_mandatory_files(
    mandatory_files: list[str],
    selected_files: list[str],
    files_content: dict[str, str],
    total_tokens: int,
    token_budget: int,
    token_counter: TokenCounter,
) -> int:
    """Add mandatory files to selection.

    Args:
        mandatory_files: List of mandatory file names
        selected_files: List of selected files to update
        files_content: File contents
        total_tokens: Current token count
        token_budget: Token budget
        token_counter: Token counter instance

    Returns:
        Updated token count
    """
    # Pre-calculate token counts for all mandatory files
    file_token_pairs = [
        (
            mandatory_file,
            token_counter.count_tokens(files_content[mandatory_file]),
        )
        for mandatory_file in mandatory_files
        if mandatory_file in files_content
    ]

    # Accumulate files that fit within budget
    current_tokens = total_tokens
    for file_name, file_tokens in file_token_pairs:
        if current_tokens + file_tokens <= token_budget:
            selected_files.append(file_name)
            current_tokens += file_tokens

    return current_tokens


def add_mandatory_files_to_priority(
    mandatory_files: list[str],
    selected_files: list[str],
    files_content: dict[str, str],
    total_tokens: int,
    token_budget: int,
    token_counter: TokenCounter,
) -> int:
    """Add mandatory files to priority selection.

    Args:
        mandatory_files: List of mandatory file names
        selected_files: List of selected files to update
        files_content: File contents
        total_tokens: Current token count
        token_budget: Token budget
        token_counter: Token counter instance

    Returns:
        Updated token count
    """
    # Pre-calculate token counts for all mandatory files
    file_token_pairs = [
        (
            mandatory_file,
            token_counter.count_tokens(files_content[mandatory_file]),
        )
        for mandatory_file in mandatory_files
        if mandatory_file in files_content
    ]

    # Accumulate files that fit within budget
    current_tokens = total_tokens
    for file_name, file_tokens in file_token_pairs:
        if current_tokens + file_tokens <= token_budget:
            selected_files.append(file_name)
            current_tokens += file_tokens
    return current_tokens


def add_high_scoring_files(
    selected_files: list[str],
    relevance_scores: dict[str, float],
    files_content: dict[str, str],
    total_tokens: int,
    token_budget: int,
    token_counter: TokenCounter,
) -> int:
    """Add high-scoring files to selection.

    Args:
        selected_files: List of selected files to update
        relevance_scores: Relevance scores
        files_content: File contents
        total_tokens: Current token count
        token_budget: Token budget
        token_counter: Token counter instance

    Returns:
        Updated token count
    """
    high_score_threshold = 0.7
    # Pre-calculate token counts for high-scoring files
    file_token_pairs = [
        (file_name, token_counter.count_tokens(files_content[file_name]))
        for file_name, score in relevance_scores.items()
        if score >= high_score_threshold
        and file_name not in selected_files
        and file_name in files_content
    ]

    # Accumulate files that fit within budget
    current_tokens = total_tokens
    for file_name, file_tokens in file_token_pairs:
        if current_tokens + file_tokens <= token_budget:
            selected_files.append(file_name)
            current_tokens += file_tokens

    return current_tokens


def add_greedy_files(
    selected_files: list[str],
    relevance_scores: dict[str, float],
    files_content: dict[str, str],
    total_tokens: int,
    token_budget: int,
    token_counter: TokenCounter,
) -> int:
    """Add files greedily by score.

    Args:
        selected_files: List of selected files to update
        relevance_scores: Relevance scores
        files_content: File contents
        total_tokens: Current token count
        token_budget: Token budget
        token_counter: Token counter instance

    Returns:
        Updated token count
    """
    # Pre-calculate token counts and sort by relevance score
    file_token_pairs = [
        (
            file_name,
            token_counter.count_tokens(files_content[file_name]),
            score,
        )
        for file_name, score in relevance_scores.items()
        if file_name not in selected_files and file_name in files_content
    ]
    file_token_pairs.sort(key=lambda x: x[2], reverse=True)

    # Accumulate files that fit within budget
    current_tokens = total_tokens
    for file_name, tokens, _ in file_token_pairs:
        if current_tokens + tokens <= token_budget:
            selected_files.append(file_name)
            current_tokens += tokens
    return current_tokens


def process_mandatory_files_with_dependencies(
    mandatory_files: list[str],
    selected_files: set[str],
    total_tokens: int,
    files_content: dict[str, str],
    token_budget: int,
    get_all_dependencies: Callable[[str], set[str]],
    token_counter: TokenCounter,
) -> tuple[set[str], int]:
    """Process mandatory files and their dependencies.

    Args:
        mandatory_files: List of mandatory file names
        selected_files: Currently selected files
        total_tokens: Current token count
        files_content: File contents
        token_budget: Token budget
        get_all_dependencies: Function to get all dependencies
        token_counter: Token counter instance

    Returns:
        Tuple of (updated selected_files, updated total_tokens)
    """
    for mandatory_file in mandatory_files:
        if mandatory_file in files_content:
            deps = get_all_dependencies(mandatory_file)
            deps.add(mandatory_file)

            cluster_tokens = calculate_cluster_tokens(
                deps, files_content, token_counter
            )

            if total_tokens + cluster_tokens <= token_budget:
                selected_files.update(deps)
                total_tokens += cluster_tokens

    return selected_files, total_tokens


def process_remaining_files_by_relevance(
    selected_files: set[str],
    total_tokens: int,
    relevance_scores: dict[str, float],
    files_content: dict[str, str],
    token_budget: int,
    get_all_dependencies: Callable[[str], set[str]],
    token_counter: TokenCounter,
) -> tuple[set[str], int]:
    """Process remaining files sorted by relevance score.

    Args:
        selected_files: Currently selected files
        total_tokens: Current token count
        relevance_scores: Relevance scores for files
        files_content: File contents
        token_budget: Token budget
        get_all_dependencies: Function to get all dependencies
        token_counter: Token counter instance

    Returns:
        Tuple of (updated selected_files, updated total_tokens)
    """
    remaining_files = [
        (file_name, score)
        for file_name, score in relevance_scores.items()
        if file_name not in selected_files
    ]
    remaining_files.sort(key=lambda x: x[1], reverse=True)

    for file_name, _ in remaining_files:
        if file_name in selected_files:
            continue

        deps = get_all_dependencies(file_name)
        deps.add(file_name)
        new_deps = deps - selected_files

        cluster_tokens = calculate_cluster_tokens(
            new_deps, files_content, token_counter
        )

        if total_tokens + cluster_tokens <= token_budget:
            selected_files.update(new_deps)
            total_tokens += cluster_tokens

    return selected_files, total_tokens


def calculate_cluster_tokens(
    dependencies: set[str], files_content: dict[str, str], token_counter: TokenCounter
) -> int:
    """Calculate total tokens for a cluster of dependencies.

    Args:
        dependencies: Set of file names in the cluster
        files_content: File contents
        token_counter: Token counter instance

    Returns:
        Total token count for the cluster
    """
    cluster_tokens = 0
    for dep in dependencies:
        if dep in files_content:
            dep_tokens = token_counter.count_tokens(files_content[dep])
            cluster_tokens += dep_tokens
    return cluster_tokens


def get_medium_scoring_files(
    relevance_scores: dict[str, float], selected_files: list[str]
) -> list[str]:
    """Get list of medium-scoring files.

    Args:
        relevance_scores: Relevance scores for files
        selected_files: Already selected files

    Returns:
        List of medium-scoring file names
    """
    medium_score_threshold = 0.4
    high_score_threshold = 0.7
    return [
        file_name
        for file_name, score in relevance_scores.items()
        if medium_score_threshold <= score < high_score_threshold
        and file_name not in selected_files
    ]
