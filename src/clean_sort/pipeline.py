"""Top-level orchestration: parse -> section reorder -> in-class sort -> render.

Public entry point: :func:`sort_source`.
"""

from __future__ import annotations

import libcst as cst

from . import undersort
from .classify import classify, is_future_import, is_module_docstring
from .config import Config
from .sorters import alpha, dependency

__all__ = ["SectionSorter", "sort_source", "would_change"]

#: Sections for which the dependency strategies (stepdown/abstraction) are valid.
_DEPENDENCY_SECTIONS = frozenset({"functions", "classes"})


class SectionSorter(cst.CSTTransformer):
    """Reorder a module's top-level statements by configured section.

    Safety model: statements whose section is not listed in ``Config.sections``
    (notably unrecognised runtime setup such as ``app = typer.Typer()``) act as
    *barriers* and never move. Recognised statements only reorder within their
    contiguous barrier-free run, so csort never moves code across a setup
    statement it might depend on. The module docstring and ``from __future__``
    imports are pinned at the top (Python requires ``__future__`` first).
    """

    def __init__(self, cfg: Config) -> None:
        self.cfg = cfg
        self._reorder_sections = set(cfg.sections)

    def leave_Module(self, original_node: cst.Module, updated_node: cst.Module) -> cst.Module:  # noqa: N802
        body = list(updated_node.body)
        if len(body) < 2:
            return updated_node

        pinned: list[cst.CSTNode] = []
        rest = body
        if is_module_docstring(body[0]):
            pinned.append(body[0])
            rest = body[1:]

        futures: list[cst.CSTNode] = []
        remainder: list[cst.CSTNode] = []
        for node in rest:
            if is_future_import(node):
                futures.append(node)
            else:
                remainder.append(node)
        pinned.extend(futures)

        tokens: list[tuple[str, object]] = []
        current: list[tuple[str, cst.CSTNode]] = []
        for node in remainder:
            section = classify(node, self.cfg)
            if section in self._reorder_sections:
                current.append((section, node))
            else:
                if current:
                    tokens.append(("seg", current))
                    current = []
                tokens.append(("barrier", node))
        if current:
            tokens.append(("seg", current))

        new_rest: list[cst.CSTNode] = []
        for kind, payload in tokens:
            if kind == "barrier":
                new_rest.append(payload)  # type: ignore[arg-type]
            else:
                new_rest.extend(self._reorder_segment(payload))  # type: ignore[arg-type]

        if pinned:
            new_body: tuple[cst.CSTNode, ...] = tuple(pinned) + tuple(new_rest)
        else:
            new_body = tuple(pinned) + _strip_leading_blanks(new_rest)

        if list(new_body) == body:
            return updated_node
        return updated_node.with_changes(body=new_body)

    def _reorder_segment(self, segment: list[tuple[str, cst.CSTNode]]) -> list[cst.CSTNode]:
        groups: dict[str, list[cst.CSTNode]] = {}
        for section, node in segment:
            groups.setdefault(section, []).append(node)
        out: list[cst.CSTNode] = []
        for section in self.cfg.sections:
            if section in groups:
                out.extend(self._sort_section(section, list(enumerate(groups[section]))))
        return out

    def _sort_section(
        self,
        section: str,
        items: list[tuple[int, cst.CSTNode]],
    ) -> list[cst.CSTNode]:
        nodes = [node for _, node in items]
        if len(nodes) < 2:
            return nodes
        strategy = self.cfg.strategy(section)
        if strategy == "alpha":
            return alpha(nodes)
        if strategy in ("stepdown", "abstraction"):
            if section in _DEPENDENCY_SECTIONS:
                return dependency(nodes, strategy)
            return alpha(nodes)
        return nodes  # "keep"


def _strip_leading_blanks(nodes: list[cst.CSTNode]) -> tuple[cst.CSTNode, ...]:
    """Drop leading blank (non-comment) lines from the first rendered node.

    Reordering can promote a node that carried two blank lines to the very top
    of the file; this trims that cosmetic artifact.
    """
    if not nodes:
        return tuple(nodes)
    first = nodes[0]
    leading = getattr(first, "leading_lines", None)
    if leading is None:
        return tuple(nodes)
    trimmed = tuple(line for line in leading if not (isinstance(line, cst.EmptyLine) and not line.comment))
    if trimmed == leading:
        return tuple(nodes)
    return (first.with_changes(leading_lines=trimmed), *nodes[1:])


def sort_source(source: str, cfg: Config, *, filename: str = "<unknown>") -> str:
    """Return ``source`` sorted according to ``cfg``.

    1. (optional) run the import engine on the raw text;
    2. parse with libcst;
    3. bail out untouched if the file is disabled (``# csort: off`` header);
    4. reorder top-level statements by section;
    5. (optional) reorder methods within each class.
    """
    module = cst.parse_module(source)
    if undersort.file_disabled(module):
        return source
    new_module = module.visit(SectionSorter(cfg))
    if cfg.class_methods_enabled:
        new_module = new_module.visit(undersort.MethodSorter(cfg.class_methods_order, cfg.class_methods_type_order))
    return new_module.code


def would_change(source: str, cfg: Config, *, filename: str = "<unknown>") -> bool:
    """True if :func:`sort_source` would alter ``source``."""
    return sort_source(source, cfg, filename=filename) != source
