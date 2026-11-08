"""Dependency-layer checker (SRS D-08, NFR-MAINT-006).

Rules enforced on ``src/widgets``:

1. A module may import only ``widgets.*`` modules of the same or a lower layer.
2. Every module must be mapped to a layer (new modules must be added to ``LAYERS``).
3. No import cycles between modules.
4. Module-level imports must be standard library or ``widgets`` (zero required runtime
   dependencies, D-12); optional third-party imports belong inside functions or ``try`` blocks.

Imports inside ``if TYPE_CHECKING:`` blocks are ignored (typing only).
Exit status 0 = clean, 1 = violations.
"""

from __future__ import annotations

import ast
import sys
from collections.abc import Mapping, Sequence
from fnmatch import fnmatchcase
from pathlib import Path

LAYERS: Sequence[tuple[str, int]] = (
    ("widgets", 9),  # public facade (lazy re-exports)
    ("widgets.errors", 0),
    ("widgets.base_elements", 0),
    ("widgets.render", 0),
    ("widgets.terminal", 0),
    ("widgets.base_elements.widget_types", 0),
    ("widgets.base_elements.import_helper", 0),
    ("widgets.base_elements.cleanup", 0),
    ("widgets.base_elements.color_manager", 1),
    ("widgets.terminal.*", 1),
    ("widgets.assets", 0),
    ("widgets.base_elements.color_data", 0),
    ("widgets.display", 0),
    ("widgets.display.*", 3),
    ("widgets.data", 0),
    ("widgets.data.*", 3),
    ("widgets.audio", 0),
    ("widgets.audio.*", 3),
    ("widgets.net", 0),
    ("widgets.net.*", 3),
    ("widgets.include", 0),
    ("widgets.include.*", 3),
    ("widgets.assets.*", 1),
    ("widgets.progress", 0),
    ("widgets.progress.state", 2),
    ("widgets.progress.meter", 2),
    ("widgets.progress.indicators", 3),
    ("widgets.progress.inline", 3),
    ("widgets.progress.tqdm", 3),
    ("widgets.render.width", 1),
    ("widgets.render.sanitize", 1),
    ("widgets.render.buffer", 1),
    ("widgets.base_elements.effects", 2),
    ("widgets.base_elements.events", 2),
    ("widgets.base_elements.lifecycle", 2),
    ("widgets.base_elements.base", 2),
    ("widgets.base_elements.layout", 2),
    ("widgets.base_elements.interactive", 2),
    ("widgets.render.diff", 2),
    ("widgets.render.screen_renderer", 2),
    ("widgets.render.run", 2),
    ("widgets.include.*", 3),
    ("widgets.rss_reader", 5),
    ("widgets.weather_widget", 5),
    ("widgets.mid_player_widget", 5),
    ("widgets.music_play_widget", 5),
    ("widgets.star_wars_widget", 5),
    ("widgets.*", 4),  # remaining primitive widgets
)

STDLIB = set(sys.stdlib_module_names)


def layer_of(module: str) -> int | None:
    for pattern, layer in LAYERS:
        if module == pattern or fnmatchcase(module, pattern):
            return layer
    return None


def module_name(path: Path, root: Path) -> str:
    relative = path.relative_to(root).with_suffix("")
    parts = list(relative.parts)
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def _is_type_checking(test: ast.expr) -> bool:
    return (isinstance(test, ast.Name) and test.id == "TYPE_CHECKING") or (
        isinstance(test, ast.Attribute) and test.attr == "TYPE_CHECKING"
    )


def _iter_imports(nodes: Sequence[ast.stmt]) -> list[ast.Import | ast.ImportFrom]:
    found: list[ast.Import | ast.ImportFrom] = []
    for node in nodes:
        if isinstance(node, ast.Import | ast.ImportFrom):
            found.append(node)
        elif isinstance(node, ast.If):
            if _is_type_checking(node.test):
                continue
            found.extend(_iter_imports(node.body))
            found.extend(_iter_imports(node.orelse))
        elif isinstance(node, ast.Try):
            for block in (node.body, node.orelse, node.finalbody):
                found.extend(_iter_imports(block))
            for handler in node.handlers:
                found.extend(_iter_imports(handler.body))
    return found


def _all_imports(tree: ast.Module) -> list[ast.Import | ast.ImportFrom]:
    """Every import, including function-local ones (for layering), minus TYPE_CHECKING blocks."""
    found: list[ast.Import | ast.ImportFrom] = []

    def visit(node: ast.AST) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.If) and _is_type_checking(child.test):
                for orelse in child.orelse:
                    visit(orelse)
                continue
            if isinstance(child, ast.Import | ast.ImportFrom):
                found.append(child)
            visit(child)

    visit(tree)
    return found


def _resolve(node: ast.Import | ast.ImportFrom, current: str, is_package: bool) -> list[str]:
    """Absolute module names imported by ``node`` (best effort, submodules included)."""
    if isinstance(node, ast.Import):
        return [alias.name for alias in node.names]
    base = node.module or ""
    if node.level:
        package = current if is_package else current.rpartition(".")[0]
        parts = package.split(".")
        parts = parts[: len(parts) - (node.level - 1)]
        base = ".".join([*parts, base] if base else parts)
    return [base, *(f"{base}.{alias.name}" for alias in node.names)]


def analyse(src_root: Path) -> tuple[list[str], Mapping[str, set[str]]]:
    problems: list[str] = []
    graph: dict[str, set[str]] = {}
    files = sorted((src_root / "widgets").rglob("*.py"))
    modules = {module_name(path, src_root): path for path in files}

    for module, path in modules.items():
        own_layer = layer_of(module)
        if own_layer is None:
            problems.append(f"{module}: not mapped to a layer (add it to LAYERS)")
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        graph[module] = set()
        is_package = path.name == "__init__.py"

        for node in _all_imports(tree):
            for target in _resolve(node, module, is_package):
                if target not in modules:
                    continue
                if target == module:
                    continue
                graph[module].add(target)
                target_layer = layer_of(target)
                if target_layer is None:
                    problems.append(f"{module}: imports unmapped module {target}")
                elif target_layer > own_layer:
                    problems.append(
                        f"{module} (L{own_layer}) imports {target} (L{target_layer}): upward import"
                    )

        for node in _iter_imports(tree.body):
            names = [alias.name for alias in node.names] if isinstance(node, ast.Import) else []
            if isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                names = [node.module]
            for name in names:
                top = name.partition(".")[0]
                if top not in STDLIB and top != "widgets":
                    problems.append(
                        f"{module}: module-level third-party import {name!r} "
                        "(make it function-local or optional)"
                    )

    problems.extend(_cycles(graph))
    return problems, graph


def _cycles(graph: Mapping[str, set[str]]) -> list[str]:
    problems: list[str] = []
    state: dict[str, int] = {}

    def dfs(node: str, stack: list[str]) -> None:
        state[node] = 1
        stack.append(node)
        for nxt in sorted(graph.get(node, ())):
            # importing a package __init__ from within it is not a real cycle
            if nxt not in graph:
                continue
            if state.get(nxt) == 1:
                cycle = [*stack[stack.index(nxt) :], nxt]
                problems.append("import cycle: " + " -> ".join(cycle))
            elif state.get(nxt) is None:
                dfs(nxt, stack)
        stack.pop()
        state[node] = 2

    for node in sorted(graph):
        if state.get(node) is None:
            dfs(node, [])
    return problems


def main(argv: Sequence[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    src_root = Path(args[0]) if args else Path(__file__).resolve().parent.parent / "src"
    problems, _ = analyse(src_root)
    for problem in problems:
        print(problem)
    if problems:
        print(f"{len(problems)} layering problem(s)")
        return 1
    print("layer check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
