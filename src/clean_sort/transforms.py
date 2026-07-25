"""Opt-in import transforms: inline-import hoisting and TYPE_CHECKING removal.

Both transforms are **pre-passes** that run before section sorting so hoisted
imports land in the ``imports`` bucket and get sorted with the rest.

Rationale (python-ultimate skill):

* **Inline imports** violate Ruff's ``PLC0415`` ("Import outside top-level").
  They bury dependencies inside function/class bodies, making the module's true
  dependency graph unclear. The fix is to move them to module level.

* **``if TYPE_CHECKING:`` guards** diverge runtime from type-checker behaviour:
  guarded imports never run, yet type checkers treat them as if they do, creating
  two different "views" of a module. Modern Python (PEP 563, ``from __future__
  import annotations``) makes them unnecessary. The fix is to dissolve the guard
  and use a normal top-level import.

Both transforms are **potentially breaking**: they change import timing. They
are opt-in (``Config.hoist_inline_imports`` / ``Config.remove_type_checking``)
and default to ``False``.
"""

from __future__ import annotations

from collections.abc import Sequence

import libcst as cst

__all__ = [
    "InlineImportHoister",
    "TypeCheckingRemover",
    "apply_transforms",
]


class _ImportExtractor(cst.CSTVisitor):
    """Walk a function body and collect import statements in order.

    Only visits the *immediate* statements of the body — does not descend into
    nested functions, classes, or compound statements (``if``/``try``/etc.).
    """

    def __init__(self) -> None:
        self.found: list[cst.BaseSmallStatement] = []

    def visit_FunctionDef(self, node: cst.FunctionDef) -> bool:  # noqa: N802, PLR6301
        return False  # don't descend into nested functions

    def visit_ClassDef(self, node: cst.ClassDef) -> bool:  # noqa: N802, PLR6301
        return False  # don't descend into nested classes

    def visit_SimpleStatementLine(self, node: cst.SimpleStatementLine) -> None:  # noqa: N802, PLR6301
        for stmt in node.body:
            if _is_simple_import(stmt):
                self.found.append(stmt)


# --------------------------------------------------------- inline import hoist
class InlineImportHoister(cst.CSTTransformer):
    """Move ``import``/``from ... import`` statements out of function bodies.

    Visits each top-level (and nested) ``FunctionDef``, extracts any import
    statements directly in its body, and prepends them to the module's import
    section. The extracted lines are removed from the function body.

    Only imports that are *direct children* of a function body are hoisted —
    imports inside ``if``/``try``/``with`` blocks within the function are left
    alone (they usually guard optional dependencies or conditional logic).
    Imports inside nested functions are also left in place.
    """

    def __init__(self) -> None:
        self._hoisted: list[cst.SimpleStatementLine] = []

    def visit_FunctionDef(self, node: cst.FunctionDef) -> bool:  # noqa: N802, PLR6301
        # Only process the outermost FunctionDef; return False to prevent
        # descending into nested FunctionDefs.
        return False

    def leave_FunctionDef(  # noqa: N802
        self, original_node: cst.FunctionDef, updated_node: cst.FunctionDef
    ) -> cst.FunctionDef:
        if not isinstance(updated_node.body, cst.IndentedBlock):
            return updated_node

        body_items = list(updated_node.body.body)
        extractor = _ImportExtractor()
        for item in body_items:
            item.visit(extractor)

        if not extractor.found:
            return updated_node

        # Remove the hoisted lines from the function body.
        hoisted_ids = {id(s) for s in extractor.found}
        new_body_items: list[cst.BaseStatement] = []
        for item in body_items:
            if isinstance(item, cst.SimpleStatementLine):
                remaining = [s for s in item.body if id(s) not in hoisted_ids]
                if remaining:
                    new_body_items.append(item.with_changes(body=remaining))
                # else: the entire line was imports — drop it
            else:
                new_body_items.append(item)

        for stmt in extractor.found:
            self._hoisted.append(_flat_import_line(stmt))

        return updated_node.with_changes(body=updated_node.body.with_changes(body=new_body_items))

    def leave_Module(self, original_node: cst.Module, updated_node: cst.Module) -> cst.Module:  # noqa: N802
        if not self._hoisted:
            return updated_node

        body = list(updated_node.body)
        deduped = _deduplicate_imports(body, self._hoisted)
        insert_at = _import_insertion_point(body)
        new_body = body[:insert_at] + deduped + body[insert_at:]
        return updated_node.with_changes(body=new_body)


# ------------------------------------------------------- TYPE_CHECKING removal
class TypeCheckingRemover(cst.CSTTransformer):
    """Delete ``if TYPE_CHECKING:`` guards and hoist their imports to the top.

    For each top-level ``if TYPE_CHECKING:`` (or ``if typing.TYPE_CHECKING:``)
    block, the contained import statements are extracted, de-indented, and
    prepended to the module's import section. The dead ``if`` guard itself is
    removed.
    """

    def __init__(self) -> None:
        self._hoisted: list[cst.SimpleStatementLine] = []

    def leave_Module(self, original_node: cst.Module, updated_node: cst.Module) -> cst.Module:  # noqa: N802
        body = list(updated_node.body)
        new_body: list[cst.CSTNode] = []
        removed = False

        for node in body:
            if isinstance(node, cst.If) and _is_type_checking_test(node.test):
                extracted = _extract_imports_from_if(node)
                if extracted is not None:
                    self._hoisted.extend(extracted)
                    removed = True
                    continue
            new_body.append(node)

        if not removed:
            return updated_node

        # Remove now-unused ``TYPE_CHECKING`` name from ``from typing import``.
        new_body = _strip_unused_type_checking(new_body)

        insert_at = _import_insertion_point(new_body)
        deduped = _deduplicate_imports(new_body[:insert_at], self._hoisted)
        result_body = new_body[:insert_at] + deduped + new_body[insert_at:]
        return updated_node.with_changes(body=result_body)


# --------------------------------------------------------------------- helpers
def _is_simple_import(stmt: cst.BaseSmallStatement) -> bool:
    """True for ``import x`` or ``from x import y`` (the hoistable kinds)."""
    return isinstance(stmt, (cst.Import, cst.ImportFrom))


def _flat_import_line(stmt: cst.BaseSmallStatement) -> cst.SimpleStatementLine:
    """Wrap a small statement as a clean top-level statement line."""
    return cst.SimpleStatementLine(body=[stmt])


def _is_type_checking_test(test: cst.BaseExpression) -> bool:
    """True when the test expression is ``TYPE_CHECKING`` or ``X.TYPE_CHECKING``."""
    if isinstance(test, cst.Name):
        return test.value == "TYPE_CHECKING"
    if isinstance(test, cst.Attribute):
        return test.attr.value == "TYPE_CHECKING"
    return False


def _extract_imports_from_if(node: cst.If) -> list[cst.SimpleStatementLine] | None:
    """Extract import statements from an ``if TYPE_CHECKING:`` block.

    Returns ``None`` if the block contains non-import statements (in which case
    the transform is skipped for safety — the block may have runtime side
    effects we don't understand).
    """
    imports: list[cst.SimpleStatementLine] = []

    def _collect(stmts: cst.BaseSuite | list[cst.BaseStatement]) -> bool:
        if isinstance(stmts, cst.IndentedBlock):
            items = stmts.body
        elif isinstance(stmts, list):
            items = stmts
        else:
            return False

        for item in items:
            if isinstance(item, cst.SimpleStatementLine):
                if all(_is_simple_import(s) for s in item.body) and item.body:
                    imports.append(item)
                else:
                    return False  # non-import statement in the block
            else:
                return False  # nested compound statement
        return True

    if not _collect(node.body):
        return None

    # Handle elif/orelse chains — only dissolve if the entire chain is imports.
    current = node.orelse
    while current is not None:
        if isinstance(current, cst.If):
            if not _collect(current.body):
                return None
            current = current.orelse
        elif isinstance(current, cst.IndentedBlock):
            if not _collect(current):
                return None
            current = None
        else:
            return None

    return imports


# ------------------------------------------------------------- pipeline wiring
def _import_insertion_point(body: Sequence[cst.CSTNode]) -> int:
    """Index after the last consecutive import run from the top.

    Skips the module docstring and ``from __future__`` imports (which must stay
    pinned), then finds the end of the contiguous import block.
    """
    idx = 0

    # Skip module docstring
    if body and _is_module_docstring(body[0]):
        idx += 1

    # Skip __future__ imports
    while idx < len(body) and _is_future_import(body[idx]):
        idx += 1

    # Advance past consecutive import lines
    while idx < len(body) and _is_import_line(body[idx]):
        idx += 1

    return idx


def _is_module_docstring(node: cst.CSTNode) -> bool:
    if not isinstance(node, cst.SimpleStatementLine) or len(node.body) != 1:
        return False
    stmt = node.body[0]
    return isinstance(stmt, cst.Expr) and isinstance(stmt.value, (cst.SimpleString, cst.ConcatenatedString))


def _is_future_import(node: cst.CSTNode) -> bool:
    if not isinstance(node, cst.SimpleStatementLine):
        return False
    return any(isinstance(stmt, cst.ImportFrom) and _dotted(stmt.module) == "__future__" for stmt in node.body)


def _is_import_line(node: cst.CSTNode) -> bool:
    if not isinstance(node, cst.SimpleStatementLine):
        return False
    return bool(node.body) and all(isinstance(s, (cst.Import, cst.ImportFrom)) for s in node.body)


def _dotted(expr: cst.BaseExpression | None) -> str:
    parts: list[str] = []
    while isinstance(expr, cst.Attribute):
        parts.append(expr.attr.value)
        expr = expr.value
    if isinstance(expr, cst.Name):
        parts.append(expr.value)
    return ".".join(reversed(parts))


def _import_signature(stmt: cst.BaseSmallStatement) -> str | None:
    """A canonical string key for an import statement (for dedup).

    Returns ``None`` for statements we don't deduplicate (anything that isn't
    a plain ``import`` or ``from`` import), or for ``from ... import *``.
    """
    if isinstance(stmt, cst.Import):
        return "import:" + ",".join(sorted(_dotted(a.name) + " as " + (_alias_name(a.asname) if a.asname else "") for a in stmt.names))
    if isinstance(stmt, cst.ImportFrom):
        if isinstance(stmt.names, cst.ImportStar):
            return None
        module = _dotted(stmt.module)
        names = sorted(
            (a.name.value if isinstance(a.name, cst.Name) else _dotted(a.name)) + (" as " + _alias_name(a.asname) if a.asname else "") for a in stmt.names
        )
        return f"from:{module}:{','.join(names)}"
    return None


def _alias_name(asname: cst.AsName) -> str:
    """Extract the textual name from an ``AsName`` (handles ``Name`` only)."""
    if isinstance(asname.name, cst.Name):
        return asname.name.value
    return ""


def _deduplicate_imports(existing: Sequence[cst.CSTNode], hoisted: list[cst.SimpleStatementLine]) -> list[cst.SimpleStatementLine]:
    """Return ``hoisted`` with entries that already exist in ``existing`` removed.

    Compares import signatures so that ``import json`` hoisted from two
    functions collapses to a single line.
    """
    seen: set[str] = set()
    for node in existing:
        if isinstance(node, cst.SimpleStatementLine):
            for stmt in node.body:
                sig = _import_signature(stmt)
                if sig is not None:
                    seen.add(sig)

    result: list[cst.SimpleStatementLine] = []
    for line in hoisted:
        for stmt in line.body:
            sig = _import_signature(stmt)
            if sig is not None and sig in seen:
                continue
            if sig is not None:
                seen.add(sig)
            result.append(line)
    return result


def _strip_unused_type_checking(body: Sequence[cst.CSTNode]) -> list[cst.CSTNode]:
    """Remove ``TYPE_CHECKING`` from ``from typing import ...`` if unused.

    If it was the only imported name, the entire line is dropped. Otherwise the
    name is removed from the import list.

    "Unused" means ``TYPE_CHECKING`` does not appear as a bare name *outside*
    of import statements (the import itself doesn't count).
    """
    # Check if TYPE_CHECKING is still referenced anywhere outside imports.
    non_import_nodes = [n for n in body if not (isinstance(n, cst.SimpleStatementLine) and _is_import_line(n))]
    referenced = _all_referenced_names(non_import_nodes)
    if "TYPE_CHECKING" in referenced:
        return list(body)

    new_body: list[cst.CSTNode] = []
    for node in body:
        if isinstance(node, cst.SimpleStatementLine):
            new_smalls: list[cst.BaseSmallStatement] = []
            for stmt in node.body:
                if isinstance(stmt, cst.ImportFrom) and _dotted(stmt.module) == "typing":
                    if isinstance(stmt.names, cst.ImportStar):
                        updated = stmt
                        new_smalls.append(updated)
                        continue
                    remaining = [a for a in stmt.names if not (isinstance(a.name, cst.Name) and a.name.value == "TYPE_CHECKING")]
                    if not remaining:
                        continue  # drop the entire ImportFrom
                    updated = stmt.with_changes(names=remaining)
                else:
                    updated = stmt
                new_smalls.append(updated)
            if new_smalls:
                new_body.append(node.with_changes(body=new_smalls))
            # else: drop the now-empty line
        else:
            new_body.append(node)
    return new_body


def _all_referenced_names(body: Sequence[cst.CSTNode]) -> set[str]:
    """Collect all bare ``Name`` tokens referenced across ``body``."""
    names: set[str] = set()

    class _Collector(cst.CSTVisitor):
        def visit_Name(self, node: cst.Name) -> None:  # noqa: N802, PLR6301
            names.add(node.value)

    for node in body:
        node.visit(_Collector())
    return names


def apply_transforms(module: cst.Module, cfg) -> cst.Module:  # noqa: ANN001
    """Run enabled import transforms on ``module`` (pre-pass before sorting).

    Transforms run in order: TYPE_CHECKING removal first, then inline-import
    hoisting, so that imports dissolved from guards are available before
    inline hoisting runs.
    """
    if getattr(cfg, "remove_type_checking", False):
        module = module.visit(TypeCheckingRemover())
    if getattr(cfg, "hoist_inline_imports", False):
        module = module.visit(InlineImportHoister())
    return module
