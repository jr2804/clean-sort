"""Classification of top-level libcst statements into section buckets.

The classifier maps each top-level statement of a module to one section key.
Unrecognised statements fall back to :attr:`Config.unknown_section`.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass

import libcst as cst

__all__ = [
    "ClassifyContext",
    "classify",
    "has_future_annotations",
    "is_future_import",
    "is_module_docstring",
    "module_top_level_names",
    "primary_name",
    "referenced_names",
]


_ENUM_SUFFIXES = ("Enum", "Flag")

@dataclass
class ClassifyContext:
    """Context passed to :func:`classify` for forward-reference detection.

    Attributes:
        later_names_by_section: Maps each configured section to the set of
            names defined in a *later* section. An assignment classified into
            section ``S`` whose RHS references any name in
            ``later_names_by_section[S]`` is treated as a barrier, preventing
            ``NameError`` at import time.
        exclude_annotation_names: When true, names that appear only in
            ``AnnAssign`` annotations are excluded from the forward-reference
            check (safe when ``from __future__ import annotations`` is active).
    """

    later_names_by_section: dict[str, set[str]]
    exclude_annotation_names: bool = False


def is_module_docstring(node: cst.CSTNode) -> bool:
    """True when ``node`` is the module docstring expression statement."""
    if not isinstance(node, cst.SimpleStatementLine) or len(node.body) != 1:
        return False
    stmt = node.body[0]
    return isinstance(stmt, cst.Expr) and isinstance(stmt.value, (cst.SimpleString, cst.ConcatenatedString))


def is_future_import(node: cst.CSTNode) -> bool:
    """True when ``node`` is a ``from __future__ import ...`` statement line."""
    if not isinstance(node, cst.SimpleStatementLine):
        return False
    return any(isinstance(stmt, cst.ImportFrom) and _dotted(stmt.module) == "__future__" for stmt in node.body)


def classify(node: cst.CSTNode, cfg, *, ctx: ClassifyContext | None = None) -> str:  # noqa: ANN001, PLR0911 - duck-typed Config
    """Classify a top-level statement into a section key.

    When ``ctx`` is provided, a ``module_constants`` assignment whose RHS
    references a name defined later in the module is downgraded to
    :attr:`Config.unknown_section` (treated as a barrier), preventing
    ``NameError`` at import time.
    """
    if isinstance(node, cst.If):
        if _is_main_guard(node):
            return "main_block"
        if _is_type_checking(node):
            return "typing_imports"
        return cfg.unknown_section
    if isinstance(node, cst.FunctionDef):
        return "functions"
    if isinstance(node, cst.ClassDef):
        if _is_dataclass(node):
            return "dataclasses"
        if _is_enum(node):
            return "enums"
        return "classes"
    if isinstance(node, cst.SimpleStatementLine):
        smalls = list(node.body)
        if smalls and all(isinstance(s, (cst.Import, cst.ImportFrom)) for s in smalls):
            return "imports"
        if _is_constant_assignment(node, cfg):
            if ctx is not None and _has_forward_ref(node, ctx, "module_constants"):
                return cfg.unknown_section
            return "module_constants"
        if _is_runtime_setup_assignment(node):
            if ctx is not None and _has_forward_ref(node, ctx, "runtime_setup"):
                return cfg.unknown_section
            return "runtime_setup"
    return cfg.unknown_section


# ------------------------------------------------------------------ predicates
def _is_main_guard(if_node: cst.If) -> bool:
    names, strings = _expr_atoms(if_node.test)
    return "__name__" in names and "__main__" in strings


def _is_type_checking(if_node: cst.If) -> bool:
    test = if_node.test
    if isinstance(test, (cst.Name, cst.Attribute)):
        atom = test.attr.value if isinstance(test, cst.Attribute) else test.value
        return atom == "TYPE_CHECKING"
    return False


def _is_enum(class_node: cst.ClassDef) -> bool:
    for arg in class_node.bases:
        value = arg.value
        attr = value.attr.value if isinstance(value, cst.Attribute) else None
        name = value.value if isinstance(value, cst.Name) else None
        token = attr or name or ""
        if token.endswith(_ENUM_SUFFIXES):
            return True
    return False


def _is_dataclass(class_node: cst.ClassDef) -> bool:
    for decorator in class_node.decorators:
        inner = decorator.decorator
        ident = inner.attr.value if isinstance(inner, cst.Attribute) else None
        if ident is None and isinstance(inner, cst.Name):
            ident = inner.value
        if ident == "dataclass":
            return True
    return False


def has_future_annotations(module: cst.Module) -> bool:
    """True when the module has ``from __future__ import annotations``."""
    for node in module.body:
        if not isinstance(node, cst.SimpleStatementLine):
            continue
        for stmt in node.body:
            if isinstance(stmt, cst.ImportFrom) and _dotted(stmt.module) == "__future__":
                if isinstance(stmt.names, cst.ImportStar):
                    continue
                for alias in stmt.names:
                    if isinstance(alias, cst.ImportAlias) and isinstance(alias.name, cst.Name) and alias.name.value == "annotations":
                        return True
    return False


def module_top_level_names(body: Sequence[cst.CSTNode]) -> dict[str, int]:
    """Map each name bound at module scope to its body index.

    Covers ``FunctionDef``, ``ClassDef``, ``Import`` / ``ImportFrom`` aliases,
    ``Assign`` / ``AnnAssign`` targets (simple ``Name`` only), and ``TypeAlias``.
    """
    index: dict[str, int] = {}
    for i, node in enumerate(body):
        if isinstance(node, (cst.FunctionDef, cst.ClassDef)):
            index[node.name.value] = i
        elif isinstance(node, cst.SimpleStatementLine):
            for stmt in node.body:
                if isinstance(stmt, cst.Import):
                    for alias in stmt.names:
                        name = alias.asname or alias.name
                        if isinstance(name, cst.Name):
                            index[name.value] = i
                elif isinstance(stmt, cst.ImportFrom):
                    if isinstance(stmt.names, cst.ImportStar):
                        continue  # ``from x import *`` — can't enumerate names
                    for alias in stmt.names:  # type: ignore[not-iterable]
                        name = alias.asname or alias.name
                        if isinstance(name, cst.Name):
                            index[name.value] = i
                elif isinstance(stmt, cst.Assign):
                    for target in stmt.targets:
                        if isinstance(target.target, cst.Name):
                            index[target.target.value] = i
                elif isinstance(stmt, cst.AnnAssign) and isinstance(stmt.target, cst.Name):
                    index[stmt.target.value] = i
        elif isinstance(node, cst.TypeAlias) and isinstance(node.name, cst.Name):
            index[node.name.value] = i
    return index


def _has_forward_ref(node: cst.CSTNode, ctx: ClassifyContext, section: str) -> bool:
    """True when ``node`` (an assignment in ``section``) references a name defined later.

    ``section`` is the section the assignment is being classified into. A name
    is a forward reference if it is defined in any section that comes after
    ``section`` in the configured order.
    """
    names = referenced_names(node)
    # Remove the node's own primary name (an assignment target is not a forward ref).
    primary = primary_name(node)
    if primary:
        names.discard(primary)
    # When ``from __future__ import annotations`` is active, annotation-only
    # names in ``AnnAssign`` are not evaluated at runtime. Subtract only names
    # that appear *exclusively* in the annotation — a name that also appears in
    # the value IS a runtime reference and must remain.
    if ctx.exclude_annotation_names and isinstance(node, cst.SimpleStatementLine):
        value_names: set[str] = set()
        annotation_names: set[str] = set()
        for stmt in node.body:
            if isinstance(stmt, cst.AnnAssign):
                if stmt.annotation is not None:
                    annotation_names |= referenced_names(stmt.annotation)
                if stmt.value is not None:
                    value_names |= referenced_names(stmt.value)
        # Only drop annotation names that do NOT also appear in the value.
        names -= annotation_names - value_names
    later = ctx.later_names_by_section.get(section, set())
    return bool(names & later)


def _is_runtime_setup_assignment(node: cst.SimpleStatementLine) -> bool:
    """True when ``node`` is a module-level assignment line.

    The complement of :func:`_is_constant_assignment` (called only after that
    returns ``False``): a statement whose smalls are all ``Assign``/``AnnAssign``
    but whose target is not a constant — e.g. ``logger = get_logger(__name__)``,
    ``app = typer.Typer()``, or a tuple unpacking ``a, b = init()``. Such
    statements classify into the ``runtime_setup`` section.
    """
    smalls = list(node.body)
    return bool(smalls) and all(isinstance(s, (cst.Assign, cst.AnnAssign)) for s in smalls)


def _is_constant_assignment(node: cst.SimpleStatementLine, cfg) -> bool:  # noqa: ANN001
    smalls = list(node.body)
    if not smalls or not all(isinstance(s, (cst.Assign, cst.AnnAssign)) for s in smalls):
        return False
    pattern = re.compile(cfg.constants_pattern)
    dunder = re.compile(r"^__.+__$")
    for stmt in smalls:
        name = None
        if isinstance(stmt, cst.Assign):
            for target in stmt.targets:
                if isinstance(target.target, cst.Name):
                    name = target.target.value
                    break
        elif isinstance(stmt, cst.AnnAssign) and isinstance(stmt.target, cst.Name):
            name = stmt.target.value
        if name is None or not (pattern.match(name) or dunder.match(name)):
            return False
    return True


# --------------------------------------------------------------------- helpers
def _expr_atoms(expr: cst.BaseExpression) -> tuple[set[str], set[str]]:
    """Return (names, string-literals-without-quotes) referenced in ``expr``."""
    names: set[str] = set()
    strings: set[str] = set()

    class _Collector(cst.CSTVisitor):
        def visit_Name(self, node: cst.Name) -> None:  # noqa: N802, PLR6301
            names.add(node.value)

        def visit_SimpleString(self, node: cst.SimpleString) -> None:  # noqa: N802, PLR6301
            strings.add(node.value.strip("'\""))

    expr.visit(_Collector())
    return names, strings


def _dotted(expr: cst.BaseExpression | None) -> str:
    """Render a dotted name expression (``a.b.c``) as a string."""
    parts: list[str] = []
    while isinstance(expr, cst.Attribute):
        parts.append(expr.attr.value)
        expr = expr.value
    if isinstance(expr, cst.Name):
        parts.append(expr.value)
    return ".".join(reversed(parts))


def primary_name(node: cst.CSTNode) -> str:
    """A stable sort key derived from a statement's primary symbol.

    For functions/classes it is the def name; for imports the module path; for
    constant assignments the target name. Anything else returns the empty string.
    """
    if isinstance(node, (cst.FunctionDef, cst.ClassDef)):
        return node.name.value
    if isinstance(node, cst.SimpleStatementLine) and node.body:
        first = node.body[0]
        if isinstance(first, cst.Import) and first.names:
            return _dotted(first.names[0].name)
        if isinstance(first, cst.ImportFrom):
            return _dotted(first.module)
        if isinstance(first, cst.Assign) and first.targets:
            target = first.targets[0].target
            if isinstance(target, cst.Name):
                return target.value
        if isinstance(first, cst.AnnAssign) and isinstance(first.target, cst.Name):
            return first.target.value
    return ""


def referenced_names(node: cst.CSTNode) -> set[str]:
    """All bare ``Name`` tokens referenced anywhere inside ``node``."""
    names: set[str] = set()

    class _Collector(cst.CSTVisitor):
        def visit_Name(self, node: cst.Name) -> None:  # noqa: N802, PLR6301
            names.add(node.value)

    node.visit(_Collector())
    return names
