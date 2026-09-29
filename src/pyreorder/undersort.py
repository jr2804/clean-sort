"""In-class method sorting (undersort semantics).

This module is an adapted reimplementation of `undersort` by Kivikood
(https://github.com/kivicode/undersort), released under the MIT License:

    Copyright (c) Kivikood / kivicode

It reorders the methods of each class by visibility (public, protected,
private) and then by method type (instance, class, static), preserving the
original relative order within each group. Non-method statements keep their
leading/trailing position. ``# nosort`` (undersort) and ``# preorder: off``
comments on a class opt that class out.

Compared to upstream, the within-group reordering was simplified to a plain
stable sort (the visibility/type grouping and configuration are unchanged).
"""

from __future__ import annotations

from collections import defaultdict

import libcst as cst

_ALL_VIS = ("public", "protected", "private")
_ALL_MTYPES = ("instance", "class", "static")
_DISABLE_MARKERS = ("preorder: off", "nosort")


class MethodSorter(cst.CSTTransformer):
    """Reorder methods within each class by visibility then method type."""

    def __init__(self, order: list[str] | None = None, method_type_order: list[str] | None = None) -> None:
        self.order = list(order) if order else list(_ALL_VIS)
        self.method_type_order = list(method_type_order) if method_type_order else list(_ALL_MTYPES)
        self.modified = False

    def leave_ClassDef(self, original_node: cst.ClassDef, updated_node: cst.ClassDef) -> cst.ClassDef:  # noqa: N802
        if has_disable_comment(updated_node):
            return updated_node

        body_items = list(updated_node.body.body)
        methods = [(i, m) for i, m in enumerate(body_items) if isinstance(m, cst.FunctionDef)]
        if not methods:
            return updated_node

        groups: dict[tuple[str, str], list[tuple[int, cst.FunctionDef]]] = defaultdict(list)
        locked: list[tuple[int, cst.FunctionDef]] = []
        for idx, method in methods:
            if has_disable_comment(method):
                locked.append((idx, method))
            else:
                key = (method_visibility(method.name.value), method_type(method))
                groups[key].append((idx, method))

        ordered_keys = self._ordered_keys()
        new_methods: list[tuple[int, cst.FunctionDef]] = []
        for key in ordered_keys:
            for item in groups.get(key, ()):
                new_methods.append(item)
        # any group not covered by the configured order (defensive: don't drop)
        for key, items in groups.items():
            if key not in ordered_keys:
                new_methods.extend(items)
        # re-insert locked (nosort) methods at their original indices
        for locked_item in locked:
            insert_at = len(new_methods)
            for pos, (existing_idx, _) in enumerate(new_methods):
                if locked_item[0] < existing_idx:
                    insert_at = pos
                    break
            new_methods.insert(insert_at, locked_item)

        if [m for _, m in methods] != [m for _, m in new_methods]:
            self.modified = True

        leading_non_methods = []
        trailing_non_methods = []
        seen_method = False
        for item in body_items:
            if isinstance(item, cst.FunctionDef):
                seen_method = True
            elif seen_method:
                trailing_non_methods.append(item)
            else:
                leading_non_methods.append(item)

        new_body = leading_non_methods + [m for _, m in new_methods] + trailing_non_methods
        return updated_node.with_changes(body=updated_node.body.with_changes(body=new_body))

    def _ordered_keys(self) -> list[tuple[str, str]]:
        keys: list[tuple[str, str]] = []
        for vis in self.order + [v for v in _ALL_VIS if v not in self.order]:
            for mtype in self.method_type_order + [m for m in _ALL_MTYPES if m not in self.method_type_order]:
                keys.append((vis, mtype))
        return keys


def _comment_disabled(comment_text: str | None) -> bool:
    if not comment_text:
        return False
    lowered = comment_text.lower()
    return any(marker in lowered for marker in _DISABLE_MARKERS)


def has_disable_comment(node: cst.FunctionDef | cst.ClassDef) -> bool:
    """True if a class/method carries a ``# preorder: off`` / ``# nosort`` comment."""
    for line in getattr(node, "leading_lines", ()) or ():
        if isinstance(line, cst.EmptyLine) and _comment_disabled(line.comment and line.comment.value):
            return True
    body = getattr(node, "body", None)
    header = getattr(body, "header", None)
    return bool(isinstance(header, cst.TrailingWhitespace) and _comment_disabled(header.comment and header.comment.value))


def file_disabled(module: cst.Module) -> bool:
    """True if the module header carries a file-level disable directive."""
    for line in module.header:
        if isinstance(line, cst.EmptyLine) and line.comment:
            text = line.comment.value.lower()
            if any(m in text for m in _DISABLE_MARKERS):
                return True
    return False


def method_visibility(name: str) -> str:
    """Visibility bucket: ``public`` (incl. dunders), ``protected``, ``private``."""
    if name.startswith("__") and name.endswith("__"):
        return "public"
    if name.startswith("__"):
        return "private"
    if name.startswith("_"):
        return "protected"
    return "public"


def method_type(method: cst.FunctionDef) -> str:
    """Method kind from decorators: ``class``, ``static`` or ``instance``."""
    for decorator in method.decorators:
        inner = decorator.decorator
        ident = inner.attr.value if isinstance(inner, cst.Attribute) else None
        if ident is None and isinstance(inner, cst.Name):
            ident = inner.value
        if ident == "classmethod":
            return "class"
        if ident == "staticmethod":
            return "static"
    return "instance"


__all__ = [
    "MethodSorter",
    "file_disabled",
]
