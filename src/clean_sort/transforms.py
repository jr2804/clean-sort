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

Additionally, when an import is moved from its original context, any
``# noqa`` linter-exclusion comment attached to it is automatically stripped
— the suppression was only justified by the original location and would be
misleading at module level.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from typing import cast

import libcst as cst

#: Comment pattern that marks a linter-exclusion directive. Matches bare
#: ``noqa`` as well as scoped forms like ``noqa: E501`` or ``noqa: E501, F401``.
_NOQA_RE = re.compile(r"#\s*noqa\b", re.IGNORECASE)


# --------------------------------------------------------- inline import hoist


class InlineImportHoister(cst.CSTTransformer):
    """Move ``import``/``from ... import`` statements out of function bodies.

    Walks each function body recursively, extracting import statements at
    *any* nesting depth inside compound statements (``try``/``if``/``with``/etc.)
    and prepending them to the module's import section.

    Imports inside **nested** functions/classes are left in place (the
    recursive walker stops at ``FunctionDef``/``ClassDef`` boundaries).
    """

    def __init__(self) -> None:
        self._hoisted: list[cst.SimpleStatementLine] = []

    def visit_FunctionDef(self, node: cst.FunctionDef) -> bool:  # noqa: N802, PLR6301
        # Do NOT descend via normal visitor — we manually walk the body in
        # leave_FunctionDef via _clean_imports_at_depth, which stops at
        # nested FunctionDef/ClassDef boundaries.
        return False

    def leave_FunctionDef(  # noqa: N802
        self, original_node: cst.FunctionDef, updated_node: cst.FunctionDef
    ) -> cst.FunctionDef:
        if not isinstance(updated_node.body, cst.IndentedBlock):
            return updated_node

        cleaned_body, found = _clean_imports_at_depth(list(updated_node.body.body))
        if not found:
            return updated_node

        for stmt, original_line in found:
            flat = _flat_import_line(stmt)
            comment = original_line.trailing_whitespace.comment
            if comment is not None and _NOQA_RE.search(comment.value):
                flat = _strip_noqa_from_line(flat)
            elif comment is not None:
                new_trailing = flat.trailing_whitespace.with_changes(comment=comment, whitespace=cst.SimpleWhitespace("  "))
                flat = flat.with_changes(trailing_whitespace=new_trailing)
            self._hoisted.append(flat)

        return updated_node.with_changes(body=updated_node.body.with_changes(body=cleaned_body))

    def leave_Module(self, original_node: cst.Module, updated_node: cst.Module) -> cst.Module:  # noqa: N802
        if not self._hoisted:
            return updated_node

        body = list(updated_node.body)
        deduped = _deduplicate_imports(body, self._hoisted)
        insert_at = _import_insertion_point(body)
        new_body = body[:insert_at] + deduped + body[insert_at:]
        return updated_node.with_changes(body=new_body)


class TypeCheckingRemover(cst.CSTTransformer):
    """Delete ``if TYPE_CHECKING:`` guards and hoist their imports to the top.

    Walks the module tree recursively, dissolving ``if TYPE_CHECKING:``
    (or ``if typing.TYPE_CHECKING:``) blocks at *any* nesting depth -- inside
    functions, classes, try/if/with/for/while blocks, etc.  Contained import
    statements are extracted, de-indented, and prepended to the module's
    import section.  The dead ``if`` guard itself is removed.
    """

    def __init__(self) -> None:
        self._hoisted: list[cst.SimpleStatementLine] = []

    def visit_FunctionDef(self, node: cst.FunctionDef) -> bool:  # noqa: N802, PLR6301
        # Do NOT descend via normal visitor -- we manually walk the tree in
        # leave_Module via _clean_type_checking_at_depth, which handles all
        # compound statement types including FunctionDef/ClassDef.
        return False

    def visit_ClassDef(self, node: cst.ClassDef) -> bool:  # noqa: N802, PLR6301
        return False

    def leave_Module(self, original_node: cst.Module, updated_node: cst.Module) -> cst.Module:  # noqa: N802
        body = list(updated_node.body)
        new_body = _clean_type_checking_at_depth(body, self._hoisted)
        if not self._hoisted:
            return updated_node

        # Remove now-unused ``TYPE_CHECKING`` name from ``from typing import``.
        new_body = _strip_unused_type_checking(new_body)

        insert_at = _import_insertion_point(new_body)
        deduped = _deduplicate_imports(new_body[:insert_at], self._hoisted)
        result_body = new_body[:insert_at] + deduped + new_body[insert_at:]
        return updated_node.with_changes(body=result_body)


# --------------------------------------------------------- inline import hoist
def _clean_imports_at_depth(
    stmts: Sequence[cst.CSTNode],
) -> tuple[list[cst.BaseStatement], list[tuple[cst.BaseSmallStatement, cst.SimpleStatementLine]]]:
    """Recursively remove import statements from ``stmts`` at any depth.

    Handles compound statements (``If``, ``Try``, ``With``, ``For``, ``While``),
    their sub-bodies (orelse, except handlers, finally), and ``IndentedBlock``.
    Does **not** descend into nested ``FunctionDef`` or ``ClassDef``.

    Returns ``(cleaned_statements, collected_imports)`` where
    ``collected_imports`` is ``(small_statement, original_line)`` pairs.
    """
    collected: list[tuple[cst.BaseSmallStatement, cst.SimpleStatementLine]] = []
    cleaned: list[cst.BaseStatement] = []

    for stmt in stmts:
        if isinstance(stmt, (cst.FunctionDef, cst.ClassDef)):
            cleaned.append(stmt)
            continue

        if isinstance(stmt, cst.SimpleStatementLine):
            non_imports: list[cst.BaseSmallStatement] = []
            for s in stmt.body:
                if _is_simple_import(s):
                    collected.append((s, stmt))
                else:
                    non_imports.append(s)
            if non_imports:
                cleaned.append(stmt.with_changes(body=non_imports))
            continue  # else: drop empty line

        if isinstance(stmt, (cst.IndentedBlock,)):
            inner_clean, inner_col = _clean_imports_at_depth(stmt.body)
            collected.extend(inner_col)
            if inner_clean:
                cleaned.append(cast(cst.BaseStatement, stmt.with_changes(body=inner_clean)))
            continue  # else: drop if empty

        if isinstance(stmt, cst.If):
            cleaned.append(_clean_if(stmt, collected))
            continue

        if isinstance(stmt, cst.Try):
            cleaned.append(_clean_try(stmt, collected))
            continue

        if isinstance(stmt, cst.With):
            inner_clean, inner_col = _clean_imports_at_depth(stmt.body.body)
            collected.extend(inner_col)
            cleaned.append(stmt.with_changes(body=stmt.body.with_changes(body=inner_clean)))
            continue

        if isinstance(stmt, (cst.For, cst.While)):
            inner_clean, inner_col = _clean_imports_at_depth(stmt.body.body)
            collected.extend(inner_col)
            new_loop = stmt.with_changes(body=stmt.body.with_changes(body=inner_clean))
            if stmt.orelse is not None:
                orelse_clean, orelse_col = _clean_imports_at_depth(stmt.orelse.body.body)
                collected.extend(orelse_col)
                new_loop = new_loop.with_changes(orelse=stmt.orelse.with_changes(body=stmt.orelse.body.with_changes(body=orelse_clean)))
            cleaned.append(new_loop)
            continue

        # Remaining items are BaseStatement at runtime — cast is safe.
        cleaned.append(cast(cst.BaseStatement, stmt))

    return cleaned, collected


def _clean_if(node: cst.If, collected: list) -> cst.If:  # noqa: ANN001
    """Clean imports from an ``If`` node (body + orelse chain)."""
    inner_body, inner_col = _clean_imports_at_depth(node.body.body)
    collected.extend(inner_col)
    result = node.with_changes(body=node.body.with_changes(body=inner_body))

    # Walk the orelse chain (can be another If or an IndentedBlock).
    current = result.orelse
    if isinstance(current, cst.If):
        result = result.with_changes(orelse=_clean_if(current, collected))
    elif isinstance(current, cst.IndentedBlock):
        orelse_clean, orelse_col = _clean_imports_at_depth(current.body)
        collected.extend(orelse_col)
        result = result.with_changes(orelse=current.with_changes(body=orelse_clean))

    return result


def _clean_try(node: cst.Try, collected: list) -> cst.Try:  # noqa: ANN001
    """Clean imports from a ``Try`` node (body + handlers + orelse + finalbody)."""
    inner_body, inner_col = _clean_imports_at_depth(node.body.body)
    collected.extend(inner_col)
    result = node.with_changes(body=node.body.with_changes(body=inner_body))

    # Except handlers
    new_handlers: list[cst.ExceptHandler] = []
    for handler in node.handlers:
        h_clean, h_col = _clean_imports_at_depth(handler.body.body)
        collected.extend(h_col)
        new_handlers.append(handler.with_changes(body=handler.body.with_changes(body=h_clean)))
    result = result.with_changes(handlers=new_handlers)

    # Else body (Else.body is IndentedBlock)
    if node.orelse is not None:
        orelse_clean, orelse_col = _clean_imports_at_depth(node.orelse.body.body)
        collected.extend(orelse_col)
        result = result.with_changes(orelse=node.orelse.with_changes(body=node.orelse.body.with_changes(body=orelse_clean)))

    # Finally body (Finally.body is IndentedBlock)
    if node.finalbody is not None:
        final_clean, final_col = _clean_imports_at_depth(node.finalbody.body.body)
        collected.extend(final_col)
        result = result.with_changes(finalbody=node.finalbody.with_changes(body=node.finalbody.body.with_changes(body=final_clean)))

    return result


# ------------------------------------------------------- TYPE_CHECKING removal


def _clean_type_checking_at_depth(
    stmts: Sequence[cst.CSTNode],
    hoisted: list[cst.SimpleStatementLine],
) -> list[cst.BaseStatement]:
    """Recursively remove ``if TYPE_CHECKING:`` blocks from ``stmts`` at any depth.

    Descends into ``try``, ``if``, ``with``, ``for``, ``while``, ``FunctionDef``,
    and ``ClassDef`` bodies, extracting and hoisting TYPE_CHECKING-guarded imports
    wherever they appear.  Returns the cleaned statement list; appends hoisted
    import lines to ``hoisted``.
    """
    cleaned: list[cst.BaseStatement] = []

    for stmt in stmts:
        if isinstance(stmt, cst.If) and _is_type_checking_test(stmt.test):
            extracted = _extract_imports_from_if(stmt)
            if extracted is not None:
                hoisted.extend(_strip_noqa_from_line(line) for line in extracted)
                continue  # drop the entire if TYPE_CHECKING block

        if isinstance(stmt, (cst.FunctionDef, cst.ClassDef)) and isinstance(stmt.body, cst.IndentedBlock):
            inner_clean = _clean_type_checking_at_depth(stmt.body.body, hoisted)
            cleaned.append(stmt.with_changes(body=stmt.body.with_changes(body=inner_clean)))
        elif isinstance(stmt, cst.Try):
            cleaned.append(_clean_try_for_type_checking(stmt, hoisted))
        elif isinstance(stmt, cst.If):
            # non-TYPE_CHECKING if -- recurse into sub-bodies
            cleaned.append(_clean_if_for_type_checking(stmt, hoisted))
        elif isinstance(stmt, cst.With):
            inner_clean = _clean_type_checking_at_depth(stmt.body.body, hoisted)
            cleaned.append(stmt.with_changes(body=stmt.body.with_changes(body=inner_clean)))
        elif isinstance(stmt, (cst.For, cst.While)):
            inner_clean = _clean_type_checking_at_depth(stmt.body.body, hoisted)
            new_stmt = stmt.with_changes(body=stmt.body.with_changes(body=inner_clean))
            if stmt.orelse is not None:
                orelse_clean = _clean_type_checking_at_depth(stmt.orelse.body.body, hoisted)
                new_stmt = new_stmt.with_changes(orelse=stmt.orelse.with_changes(body=stmt.orelse.body.with_changes(body=orelse_clean)))
            cleaned.append(new_stmt)
        else:
            cleaned.append(cast(cst.BaseStatement, stmt))

    return cleaned


def _clean_try_for_type_checking(node: cst.Try, hoisted: list[cst.SimpleStatementLine]) -> cst.Try:
    """Clean TYPE_CHECKING blocks from a ``Try`` node's sub-bodies."""
    inner_body = _clean_type_checking_at_depth(list(node.body.body), hoisted)
    result = node.with_changes(body=node.body.with_changes(body=inner_body))

    new_handlers: list[cst.ExceptHandler] = []
    for handler in node.handlers:
        h_clean = _clean_type_checking_at_depth(list(handler.body.body), hoisted)
        new_handlers.append(handler.with_changes(body=handler.body.with_changes(body=h_clean)))
    result = result.with_changes(handlers=new_handlers)

    if node.orelse is not None:
        orelse_clean = _clean_type_checking_at_depth(list(node.orelse.body.body), hoisted)
        result = result.with_changes(orelse=node.orelse.with_changes(body=node.orelse.body.with_changes(body=orelse_clean)))

    if node.finalbody is not None:
        final_clean = _clean_type_checking_at_depth(list(node.finalbody.body.body), hoisted)
        result = result.with_changes(finalbody=node.finalbody.with_changes(body=node.finalbody.body.with_changes(body=final_clean)))

    return result


def _clean_if_for_type_checking(node: cst.If, hoisted: list[cst.SimpleStatementLine]) -> cst.If:
    """Clean TYPE_CHECKING blocks from an ``If`` node's sub-bodies (body + orelse)."""
    inner_body = _clean_type_checking_at_depth(list(node.body.body), hoisted)
    result = node.with_changes(body=node.body.with_changes(body=inner_body))

    current = result.orelse
    if isinstance(current, cst.If):
        result = result.with_changes(orelse=_clean_if_for_type_checking(current, hoisted))
    elif isinstance(current, cst.IndentedBlock):
        orelse_clean = _clean_type_checking_at_depth(list(current.body), hoisted)
        result = result.with_changes(orelse=current.with_changes(body=orelse_clean))

    return result


# --------------------------------------------------------------------- helpers
def _is_simple_import(stmt: cst.BaseSmallStatement) -> bool:
    """True for ``import x`` or ``from x import y`` (the hoistable kinds)."""
    return isinstance(stmt, (cst.Import, cst.ImportFrom))


def _flat_import_line(stmt: cst.BaseSmallStatement) -> cst.SimpleStatementLine:
    """Wrap a small statement as a clean top-level statement line."""
    return cst.SimpleStatementLine(body=[stmt])


def _strip_noqa_from_line(line: cst.SimpleStatementLine) -> cst.SimpleStatementLine:
    """Strip a ``# noqa`` linter-exclusion comment from a statement line.

    When an import is hoisted out of its original context (a function body or
    a ``TYPE_CHECKING`` guard), any ``# noqa`` suppression that was justified
    by *that* context no longer applies. This removes the trailing comment if
    it is a noqa directive, leaving other comments untouched.

    Only the line-level ``trailing_whitespace.comment`` is inspected — that is
    where ``# noqa`` attaches for ``import``/``from`` statements.
    """
    trailing = line.trailing_whitespace
    comment = trailing.comment
    if comment is None or not _NOQA_RE.search(comment.value):
        return line
    # Drop the comment and the whitespace that preceded it (would otherwise
    # leave trailing spaces before the newline).
    new_trailing = trailing.with_changes(comment=None, whitespace=cst.SimpleWhitespace(""))
    return line.with_changes(trailing_whitespace=new_trailing)


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

__all__ = [
    "InlineImportHoister",
    "TypeCheckingRemover",
    "apply_transforms",
]
