"""Graph query engine — forward/reverse/test-impact/coverage queries on unified graph."""
from __future__ import annotations

import fnmatch
from collections import deque
from typing import Any


class GraphQuery:
    """Graph query engine. Builds adjacency lists on init (ADR-6)."""

    def __init__(self, graph: dict[str, Any]) -> None:
        self._graph = graph
        self._nodes: dict[str, dict] = graph.get("nodes", {})
        self._edges: list[dict] = graph.get("edges", [])
        self._adj: dict[str, list[str]] = self._build_adj(reverse=False)
        self._reverse_adj: dict[str, list[str]] = self._build_adj(reverse=True)

    def list_nodes(self) -> list[str]:
        """Return all node keys, sorted alphabetically."""
        return sorted(self._nodes.keys())

    def resolve_node_key(self, pattern: str) -> tuple[str | None, list[str]]:
        """Resolve a node key pattern (exact or glob match).

        Returns (resolved_key, all_matches).
        - Exact match: returns (key, [key])
        - Glob match: returns (first_match, sorted_matches) or (None, []) if no match
        """
        if pattern in self._nodes:
            return (pattern, [pattern])
        matches = sorted(k for k in self._nodes if fnmatch.fnmatch(k, pattern))
        if matches:
            return (matches[0], matches)
        return (None, [])

    def _build_adj(self, *, reverse: bool) -> dict[str, list[str]]:
        """Build adjacency list from edge list."""
        adj: dict[str, list[str]] = {}
        for edge in self._edges:
            src = edge["to"] if reverse else edge["from"]
            dst = edge["from"] if reverse else edge["to"]
            adj.setdefault(src, []).append(dst)
        return adj

    def _bfs_traverse(
        self,
        start: str,
        adj: dict[str, list[str]],
        max_depth: int,
    ) -> dict[str, Any]:
        """Generic BFS traversal with Visited Set + max_depth (ADR-6).

        Returns:
        {
            "nodes": {key: node_data},
            "is_truncated": bool,
            "truncated_branches": [key, ...],
        }
        Entry node is included in visited but not in result nodes.
        """
        result_nodes: dict[str, dict] = {}
        visited: set[str] = {start}
        queue: deque[tuple[str, int]] = deque([(start, 0)])
        is_truncated = False
        truncated_branches: list[str] = []
        truncated_seen: set[str] = set()

        while queue:
            current, depth = queue.popleft()
            for neighbor in adj.get(current, []):
                if neighbor in visited:
                    continue
                visited.add(neighbor)
                if depth + 1 > max_depth:
                    is_truncated = True
                    if neighbor not in truncated_seen:
                        truncated_seen.add(neighbor)
                        truncated_branches.append(neighbor)
                    continue
                result_nodes[neighbor] = self._nodes.get(neighbor, {})
                queue.append((neighbor, depth + 1))

        return {
            "nodes": result_nodes,
            "is_truncated": is_truncated,
            "truncated_branches": truncated_branches,
        }

    def forward_from(
        self,
        start: str,
        max_depth: int = 10,
    ) -> dict[str, Any]:
        """Forward transitive traversal: all descendants of start (Q1)."""
        return self._bfs_traverse(start, self._adj, max_depth)

    def reverse_from(
        self,
        start: str,
        max_depth: int = 10,
    ) -> dict[str, Any]:
        """Reverse transitive traversal: all ancestors of start (Q2)."""
        return self._bfs_traverse(start, self._reverse_adj, max_depth)

    def test_impact(
        self,
        target: str,
        max_depth: int = 10,
    ) -> dict[str, Any]:
        """Reverse query filtered to is_test == true nodes (Q3)."""
        raw = self.reverse_from(target, max_depth)
        filtered = {
            k: v for k, v in raw["nodes"].items()
            if v.get("is_test", False)
        }
        warnings: list[str] = []
        if not filtered and not any(
            node.get("is_test", False) for node in self._nodes.values()
        ):
            warnings.append("no_test_nodes_in_graph")

        result: dict[str, Any] = {
            "nodes": filtered,
            "is_truncated": raw["is_truncated"],
            "truncated_branches": raw.get("truncated_branches", []),
        }
        if warnings:
            result["warnings"] = warnings
        return result

    def coverage(
        self,
        test: str,
        max_depth: int = 10,
    ) -> dict[str, Any]:
        """Forward query filtered to is_test == false nodes (Q4)."""
        warnings: list[str] = []
        target_node = self._nodes.get(test, {})
        if not target_node.get("is_test", False):
            warnings.append("target_is_not_test_function")

        raw = self.forward_from(test, max_depth)
        filtered = {
            k: v for k, v in raw["nodes"].items()
            if not v.get("is_test", False)
        }
        result: dict[str, Any] = {
            "nodes": filtered,
            "is_truncated": raw["is_truncated"],
            "truncated_branches": raw.get("truncated_branches", []),
        }
        if warnings:
            result["warnings"] = warnings
        return result
