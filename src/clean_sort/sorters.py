"""In-section sorting strategies.

* :func:`alpha` — stable alphabetical by primary symbol name.
* :func:`dependency` — topological order by symbol references. ``"stepdown"``
  puts callers before callees (top-down narrative); ``"abstraction"`` puts
  callees first (low-level utilities first). Cycles keep their original order.
"""

from __future__ import annotations

import heapq

import libcst as cst

from .classify import primary_name, referenced_names


def alpha(nodes: list[cst.CSTNode]) -> list[cst.CSTNode]:
    """Stable sort by ``(primary name, original index)``."""
    indexed = list(enumerate(nodes))
    indexed.sort(key=lambda item: (primary_name(item[1]).lower(), item[0]))
    return [node for _, node in indexed]


def dependency(nodes: list[cst.CSTNode], direction: str) -> list[cst.CSTNode]:
    """Order ``nodes`` by their reference graph.

    Edges: ``i -> j`` when node ``i`` references node ``j`` by name. With
    ``direction="stepdown"`` callers precede callees; with ``"abstraction"``
    callees precede callers. Self-references are ignored and cycles are broken
    by preserving original order.
    """
    count = len(nodes)
    if count < 2:
        return list(nodes)

    names = [primary_name(node) for node in nodes]
    index_by_name = {name: i for i, name in enumerate(names)}

    out_edges: list[list[int]] = []
    for i, node in enumerate(nodes):
        referenced = referenced_names(node)
        referenced.discard(names[i])
        out_edges.append(sorted({index_by_name[r] for r in referenced if r in index_by_name}))

    indegree = [0] * count
    for i in range(count):
        for j in out_edges[i]:
            indegree[j] += 1

    if direction == "abstraction":
        # For abstraction we reverse at the end, so tie-breaking among
        # same-level nodes must use the *reverse* of their original index to
        # keep the output stable (idempotent).  We achieve this by negating
        # indices in the heap.
        heap = [-i for i in range(count) if indegree[i] == 0]
        heapq.heapify(heap)
        order: list[int] = []
        visited: set[int] = set()
        while heap:
            i = -heapq.heappop(heap)
            if i in visited:
                continue
            visited.add(i)
            order.append(i)
            for j in out_edges[i]:
                indegree[j] -= 1
                if indegree[j] == 0:
                    heapq.heappush(heap, -j)

        # cyclic leftovers: keep original order
        for i in range(count):
            if i not in visited:
                visited.add(i)
                order.append(i)

        order.reverse()
    else:
        heap = [i for i in range(count) if indegree[i] == 0]
        heapq.heapify(heap)
        order = []
        visited = set()
        while heap:
            i = heapq.heappop(heap)
            if i in visited:
                continue
            visited.add(i)
            order.append(i)
            for j in out_edges[i]:
                indegree[j] -= 1
                if indegree[j] == 0:
                    heapq.heappush(heap, j)

        # cyclic leftovers: keep original order
        for i in range(count):
            if i not in visited:
                visited.add(i)
                order.append(i)

    return [nodes[i] for i in order]

__all__ = ["alpha", "dependency"]
