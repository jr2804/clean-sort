"""Classification of top-level libcst statements into section buckets.

The classifier maps each top-level statement of a module to one section key.
Unrecognised statements fall back to :attr:`Config.unknown_section`.
"""

from __future__ import annotations

import re

import libcst as cst

__all__ = [
    "classify",
    "is_future_import",
    "is_module_docstring",
    "primary_name",
    "referenced_names",
]

_ENUM_SUFFIXES = ("Enum", "Flag")


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


def classify(node: cst.CSTNode, cfg) -> str:  # noqa: ANN001, PLR0911 - duck-typed Config
    """Classify a top-level statement into a section key."""
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
            return "module_constants"
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
        elif isinstance(stmt.target, cst.Name):
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
        def visit_Name(self, n: cst.Name) -> None:  # noqa: N802, PLR6301
            names.add(n.value)

    node.visit(_Collector())
    return names
