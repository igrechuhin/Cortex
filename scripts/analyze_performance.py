#!/usr/bin/env python3
"""Analyze code for performance issues without running it.

This script analyzes the codebase for common performance anti-patterns:
- O(n²) or worse algorithms
- Inefficient string operations
- Repeated expensive operations
- Missing caching opportunities
"""

import ast
from collections import defaultdict
from pathlib import Path
from typing import TypedDict


class PerformanceIssue(TypedDict):
    """Performance issue dictionary structure."""

    type: str
    severity: str
    line: int
    function: str | None
    message: str


class PerformanceAnalyzer(ast.NodeVisitor):
    """AST visitor to detect performance anti-patterns."""

    def __init__(self, filename: str):
        self.filename = filename
        self.issues: list[PerformanceIssue] = []
        self.function_name: str | None = None
        self.nested_loops = 0
        self.loop_depth = 0

    def visit_FunctionDef(self, node: ast.FunctionDef):
        old_function = self.function_name
        self.function_name = node.name
        self.generic_visit(node)
        self.function_name = old_function

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        old_function = self.function_name
        self.function_name = node.name
        self.generic_visit(node)
        self.function_name = old_function

    def visit_For(self, node: ast.For):
        self.loop_depth += 1

        if self.loop_depth >= 2:
            self.issues.append(
                {
                    "type": "nested_loops",
                    "severity": "high",
                    "line": node.lineno,
                    "function": self.function_name,
                    "message": f"Nested loop detected (depth {self.loop_depth}) - potential O(n²) or worse",
                }
            )

        self.generic_visit(node)
        self.loop_depth -= 1

    def visit_While(self, node: ast.While):
        self.loop_depth += 1

        if self.loop_depth >= 2:
            self.issues.append(
                {
                    "type": "nested_loops",
                    "severity": "high",
                    "line": node.lineno,
                    "function": self.function_name,
                    "message": f"Nested while loop (depth {self.loop_depth}) - potential O(n²) or worse",
                }
            )

        self.generic_visit(node)
        self.loop_depth -= 1

    def visit_Attribute(self, node: ast.Attribute):
        # Check for repeated list appends in loops
        if self.loop_depth > 0 and node.attr == "append":
            if isinstance(node.value, ast.Name):
                self.issues.append(
                    {
                        "type": "list_append_in_loop",
                        "severity": "medium",
                        "line": node.lineno,
                        "function": self.function_name,
                        "message": "List append in loop - consider list comprehension",
                    }
                )

        # Check for .split() in loops
        if self.loop_depth > 0 and node.attr == "split":
            self.issues.append(
                {
                    "type": "string_split_in_loop",
                    "severity": "medium",
                    "line": node.lineno,
                    "function": self.function_name,
                    "message": "String split in loop - consider moving outside",
                }
            )

        self.generic_visit(node)

    def visit_Call(self, node: ast.Call):
        # Check for repeated file operations
        if isinstance(node.func, ast.Attribute):
            if node.func.attr in ["read_file", "write_file", "exists"]:
                if self.loop_depth > 0:
                    self.issues.append(
                        {
                            "type": "file_io_in_loop",
                            "severity": "high",
                            "line": node.lineno,
                            "function": self.function_name,
                            "message": f"File I/O ({node.func.attr}) in loop - major performance impact",
                        }
                    )

            # Check for len() in loop condition (common in while loops)
            if node.func.attr == "len" and self.loop_depth > 0:
                self.issues.append(
                    {
                        "type": "len_in_loop",
                        "severity": "low",
                        "line": node.lineno,
                        "function": self.function_name,
                        "message": "len() in loop - consider caching",
                    }
                )

        self.generic_visit(node)


def analyze_file(filepath: Path) -> list[PerformanceIssue]:
    """Analyze a Python file for performance issues."""
    try:
        with open(filepath) as f:
            content = f.read()

        tree = ast.parse(content, filename=str(filepath))
        analyzer = PerformanceAnalyzer(str(filepath))
        analyzer.visit(tree)
        return analyzer.issues
    except SyntaxError as e:
        print(f"Syntax error in {filepath}: {e}")
        return []
    except Exception as e:
        print(f"Error analyzing {filepath}: {e}")
        return []


def main():
    """Analyze all Python files in the project."""
    project_root = Path(__file__).parent.parent
    src_dir = project_root / "src" / "cortex"

    # Focus on performance-critical modules
    focus_modules = [
        "core/token_counter.py",
        "core/file_system.py",
        "core/dependency_graph.py",
        "analysis/structure_analyzer.py",
        "analysis/pattern_analyzer.py",
        "linking/transclusion_engine.py",
        "validation/duplication_detector.py",
        "optimization/context_optimizer.py",
        "optimization/optimization_strategies.py",
    ]

    all_issues: defaultdict[str, list[PerformanceIssue]] = defaultdict(list)
    total_issues = 0

    print("=" * 70)
    print("MCP Memory Bank - Performance Analysis")
    print("=" * 70)
    print()

    for module_path in focus_modules:
        filepath = src_dir / module_path
        if not filepath.exists():
            print(f"⚠️  File not found: {module_path}")
            continue

        issues = analyze_file(filepath)
        if issues:
            all_issues[module_path] = issues
            total_issues += len(issues)

            print(f"\n📁 {module_path}")
            print("-" * 70)

            # Group by severity
            by_severity: defaultdict[str, list[PerformanceIssue]] = defaultdict(list)
            for issue in issues:
                by_severity[issue["severity"]].append(issue)

            for severity in ["high", "medium", "low"]:
                if severity in by_severity:
                    for issue in by_severity[severity]:
                        severity_icon = {
                            "high": "🔴",
                            "medium": "🟡",
                            "low": "🟢",
                        }[severity]
                        print(
                            f"  {severity_icon} Line {issue['line']:4d} [{issue['function'] or 'module'}]: {issue['message']}"
                        )

    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"Total files analyzed: {len(focus_modules)}")
    print(f"Files with issues: {len(all_issues)}")
    print(f"Total issues found: {total_issues}")

    if total_issues > 0:
        print("\nIssues by severity:")
        severity_counts: defaultdict[str, int] = defaultdict(int)
        for issues in all_issues.values():
            for issue in issues:
                severity_counts[issue["severity"]] += 1

        for severity in ["high", "medium", "low"]:
            if severity in severity_counts:
                print(f"  {severity.capitalize():8s}: {severity_counts[severity]}")

        print("\nTop priority fixes:")
        high_priority: list[tuple[str, PerformanceIssue]] = []
        for module, issues in all_issues.items():
            for issue in issues:
                if issue["severity"] == "high":
                    high_priority.append((module, issue))

        for i, (module, issue) in enumerate(high_priority[:5], 1):
            print(f"  {i}. {module}:{issue['line']} - {issue['message']}")

    print("=" * 70)


if __name__ == "__main__":
    main()
