#!/usr/bin/env python3
"""Analyze module dependencies and detect circular references."""

import ast
import sys
from collections import defaultdict
from pathlib import Path


def get_module_imports(file_path: Path) -> set[str]:
    """Extract all cortex imports from a module, excluding TYPE_CHECKING imports."""
    try:
        with open(file_path) as f:
            tree = ast.parse(f.read())

        imports = set()
        type_checking_imports = set()

        # Find all TYPE_CHECKING blocks
        for node in ast.walk(tree):
            if isinstance(node, ast.If):
                # Check if this is a TYPE_CHECKING block
                if is_type_checking_block(node):
                    # Extract imports from TYPE_CHECKING block
                    for child in ast.walk(node):
                        if isinstance(child, ast.ImportFrom):
                            if child.module and child.module.startswith("cortex"):
                                parts = child.module.split(".")
                                if len(parts) >= 2:
                                    layer = parts[1] if len(parts) > 1 else parts[0]
                                    type_checking_imports.add(layer)

        # Extract all imports
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                if node.module and node.module.startswith("cortex"):
                    # Get the full module path
                    parts = node.module.split(".")
                    if len(parts) >= 2:
                        # Get layer (e.g., 'core', 'linking', 'validation')
                        layer = parts[1] if len(parts) > 1 else parts[0]
                        imports.add(layer)

        # Remove TYPE_CHECKING imports from runtime imports
        runtime_imports = imports - type_checking_imports

        return runtime_imports
    except Exception as e:
        print(f"Error parsing {file_path}: {e}", file=sys.stderr)
        return set()


def is_type_checking_block(node: ast.If) -> bool:
    """Check if an If node is a TYPE_CHECKING block."""
    if isinstance(node.test, ast.Name):
        return node.test.id == "TYPE_CHECKING"
    elif isinstance(node.test, ast.Attribute):
        # Handle typing.TYPE_CHECKING
        if isinstance(node.test.value, ast.Name):
            return node.test.value.id == "typing" and node.test.attr == "TYPE_CHECKING"
    return False


def get_module_layer(file_path: Path) -> str:
    """Determine which architectural layer a module belongs to."""
    parts = file_path.relative_to("src/cortex").parts

    if len(parts) == 0 or parts[0].endswith(".py"):
        return "root"

    return parts[0]


def analyze_dependencies() -> dict[str, set[str]]:
    """Analyze dependencies between architectural layers."""
    # Get all Python files
    files = list(Path("src/cortex").rglob("*.py"))
    files = [f for f in files if "__pycache__" not in str(f)]

    # Map layer -> set of layers it depends on
    layer_deps: dict[str, set[str]] = defaultdict(set)

    for file in files:
        layer = get_module_layer(file)
        if layer in ("__init__", "root", "templates", "guides", "resources"):
            continue

        imports = get_module_imports(file)
        for imported_layer in imports:
            if imported_layer != layer and imported_layer not in (
                "templates",
                "guides",
                "resources",
            ):
                layer_deps[layer].add(imported_layer)

    return layer_deps


def find_circular_dependencies(layer_deps: dict[str, set[str]]) -> list[list[str]]:
    """Find circular dependencies between layers."""
    cycles = []

    def dfs(node: str, path: list[str], visited: set[str]):
        if node in path:
            # Found a cycle
            cycle_start = path.index(node)
            cycle = path[cycle_start:] + [node]
            if cycle not in cycles and list(reversed(cycle)) not in cycles:
                cycles.append(cycle)
            return

        if node in visited:
            return

        visited.add(node)
        path.append(node)

        for neighbor in layer_deps.get(node, set()):
            dfs(neighbor, path.copy(), visited)

    for layer in layer_deps.keys():
        dfs(layer, [], set())

    return cycles


def main():
    """Main analysis function."""
    print("Analyzing module dependencies...")
    print()

    layer_deps = analyze_dependencies()

    # Define intended layer hierarchy
    intended_order = [
        "core",
        "linking",
        "validation",
        "optimization",
        "analysis",
        "refactoring",
        "rules",
        "structure",
        "managers",
        "tools",
        "server",
        "main",
    ]

    print("=== Layer Dependencies ===")
    print()
    for layer in intended_order:
        if layer in layer_deps:
            deps = sorted(layer_deps[layer])
            print(f"{layer}:")
            for dep in deps:
                print(f"  → {dep}")
            print()

    # Find circular dependencies
    print("=== Circular Dependencies ===")
    print()
    cycles = find_circular_dependencies(layer_deps)
    if cycles:
        print(f"Found {len(cycles)} circular dependency cycle(s):")
        print()
        for i, cycle in enumerate(cycles, 1):
            print(f"{i}. {' → '.join(cycle)}")
    else:
        print("✅ No circular dependencies found!")

    print()
    print("=== Layer Violation Analysis ===")
    print()

    # Check for violations of intended layer order
    violations = []
    layer_order_map = {layer: i for i, layer in enumerate(intended_order)}

    for layer, deps in layer_deps.items():
        layer_index = layer_order_map.get(layer, 999)
        for dep in deps:
            dep_index = layer_order_map.get(dep, 999)
            if dep_index >= layer_index:
                violations.append((layer, dep, layer_index, dep_index))

    if violations:
        print(f"Found {len(violations)} layer violation(s):")
        print()
        for layer, dep, layer_idx, dep_idx in sorted(violations):
            print(f"  ⚠️  {layer} (level {layer_idx}) → {dep} (level {dep_idx})")
    else:
        print("✅ All dependencies follow the intended layer hierarchy!")


if __name__ == "__main__":
    main()
