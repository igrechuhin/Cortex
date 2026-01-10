"""Analyze code complexity across the codebase.

Generates a report of functions with high cyclomatic or cognitive
complexity, nesting depth, and other maintainability metrics.

Usage:
    python scripts/analyze_complexity.py

Output:
    - Report of high-complexity functions
    - Nesting depth violations
    - Summary statistics
"""

import ast
from pathlib import Path
from typing import TypedDict


class ComplexityIssue(TypedDict):
    """Complexity issue dictionary structure."""

    file: str
    function: str
    line: int
    complexity: int
    nesting: int
    issues: list[str]


def analyze_file(file_path: Path) -> list[ComplexityIssue]:
    """Analyze a single Python file for complexity metrics.

    Args:
        file_path: Path to Python file to analyze

    Returns:
        List of complexity issues found in the file
    """
    results: list[ComplexityIssue] = []

    try:
        with open(file_path) as f:
            tree = ast.parse(f.read(), filename=str(file_path))
    except SyntaxError:
        print(f"⚠️  Syntax error in {file_path}, skipping")
        return []

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            complexity = calculate_complexity(node)
            nesting = calculate_nesting_depth(node)

            # Report functions with complexity >10 or nesting >3
            if complexity > 10 or nesting > 3:
                # Get relative path from project root
                try:
                    rel_path = file_path.relative_to(Path.cwd())
                except ValueError:
                    rel_path = file_path

                results.append(
                    {
                        "file": str(rel_path),
                        "function": node.name,
                        "line": node.lineno,
                        "complexity": complexity,
                        "nesting": nesting,
                        "issues": _describe_issues(complexity, nesting),
                    }
                )

    return results


def calculate_complexity(node: ast.AST) -> int:
    """Calculate cyclomatic complexity of a function.

    Complexity increases for:
    - Each decision point (if, while, for, with)
    - Each exception handler
    - Each boolean operator (and, or)

    Args:
        node: AST node to analyze

    Returns:
        Cyclomatic complexity score
    """
    complexity = 1  # Base complexity

    for child in ast.walk(node):
        # Decision points
        if isinstance(child, (ast.If, ast.While, ast.For, ast.With)):
            complexity += 1
        # Exception handlers
        elif isinstance(child, ast.ExceptHandler):
            complexity += 1
        # Boolean operators (and, or)
        elif isinstance(child, ast.BoolOp):
            complexity += len(child.values) - 1
        # Comprehensions with conditionals
        elif isinstance(child, (ast.ListComp, ast.SetComp, ast.DictComp)):
            for generator in child.generators:
                complexity += len(generator.ifs)

    return complexity


def calculate_nesting_depth(node: ast.AST, depth: int = 0) -> int:
    """Calculate maximum nesting depth in a function.

    Args:
        node: AST node to analyze
        depth: Current depth level

    Returns:
        Maximum nesting depth found
    """
    max_depth = depth

    for child in ast.iter_child_nodes(node):
        # Control structures that increase nesting
        if isinstance(child, (ast.If, ast.While, ast.For, ast.With, ast.Try)):
            child_depth = calculate_nesting_depth(child, depth + 1)
            max_depth = max(max_depth, child_depth)
        else:
            child_depth = calculate_nesting_depth(child, depth)
            max_depth = max(max_depth, child_depth)

    return max_depth


def _describe_issues(complexity: int, nesting: int) -> list[str]:
    """Generate human-readable issue descriptions.

    Args:
        complexity: Cyclomatic complexity score
        nesting: Maximum nesting depth

    Returns:
        List of issue descriptions
    """
    issues: list[str] = []

    if complexity > 10:
        issues.append(f"High complexity: {complexity} (target: ≤10)")

    if nesting > 3:
        issues.append(f"Deep nesting: {nesting} levels (target: ≤3)")

    return issues


def main():
    """Run complexity analysis on all source files."""
    src_path = Path("src/cortex")

    if not src_path.exists():
        print(f"❌ Source directory not found: {src_path}")
        return 1

    print("🔍 Analyzing code complexity...\n")

    all_results: list[ComplexityIssue] = []
    file_count = 0

    for py_file in sorted(src_path.rglob("*.py")):
        if "__pycache__" in str(py_file) or py_file.name.startswith("test_"):
            continue

        file_count += 1
        results = analyze_file(py_file)
        all_results.extend(results)

    # Sort by complexity (highest first), then by nesting
    def sort_key(x: ComplexityIssue) -> tuple[int, int]:
        return (x["complexity"], x["nesting"])

    all_results.sort(key=sort_key, reverse=True)

    # Print results
    print("=" * 80)
    print("COMPLEXITY ANALYSIS REPORT")
    print("=" * 80)

    if not all_results:
        print("\n✅ No complexity issues found!")
        print(f"\n📊 Analyzed {file_count} files")
        return 0

    # Group by severity
    high_complexity: list[ComplexityIssue] = [
        r for r in all_results if r["complexity"] > 15
    ]
    medium_complexity: list[ComplexityIssue] = [
        r for r in all_results if 10 < r["complexity"] <= 15
    ]
    deep_nesting: list[ComplexityIssue] = [r for r in all_results if r["nesting"] > 3]

    # Print high complexity functions
    if high_complexity:
        print(f"\n🔴 HIGH COMPLEXITY (>{15}):")
        print("-" * 80)
        for result in high_complexity:
            print(f"\n📍 {result['file']}:{result['line']}")
            print(f"   Function: {result['function']}")
            print(
                f"   Complexity: {result['complexity']} (nesting: {result['nesting']})"
            )
            for issue in result["issues"]:
                print(f"   - {issue}")

    # Print medium complexity functions
    if medium_complexity:
        print("\n🟡 MEDIUM COMPLEXITY (11-15):")
        print("-" * 80)
        for result in medium_complexity:
            print(f"\n📍 {result['file']}:{result['line']}")
            print(f"   Function: {result['function']}")
            print(
                f"   Complexity: {result['complexity']} (nesting: {result['nesting']})"
            )

    # Print deep nesting issues
    nesting_only: list[ComplexityIssue] = [
        r for r in deep_nesting if r["complexity"] <= 10
    ]
    if nesting_only:
        print("\n🟠 DEEP NESTING (>3 levels):")
        print("-" * 80)
        for result in nesting_only:
            print(f"\n📍 {result['file']}:{result['line']}")
            print(f"   Function: {result['function']}")
            print(
                f"   Nesting: {result['nesting']} levels (complexity: {result['complexity']})"
            )

    # Summary statistics
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"\n📊 Total files analyzed: {file_count}")
    print(f"🔴 High complexity functions (>15): {len(high_complexity)}")
    print(f"🟡 Medium complexity functions (11-15): {len(medium_complexity)}")
    print(f"🟠 Deep nesting functions (>3 levels): {len(nesting_only)}")
    print(f"📈 Total issues: {len(all_results)}")

    if all_results:
        complexity_values = [r["complexity"] for r in all_results]
        avg_complexity = sum(complexity_values) / len(complexity_values)
        max_complexity = max(complexity_values)
        print(f"\n📊 Average complexity (issues only): {avg_complexity:.1f}")
        print(f"📊 Maximum complexity: {max_complexity}")

    print("\n" + "=" * 80)
    print("RECOMMENDATIONS")
    print("=" * 80)
    print(
        """
1. Apply guard clauses to reduce nesting
2. Extract complex conditionals to named functions
3. Use strategy pattern for switch-like if-elif chains
4. Extract nested loops to separate methods
5. Use list comprehensions for simple iterations
"""
    )

    return 0


if __name__ == "__main__":
    exit(main())
