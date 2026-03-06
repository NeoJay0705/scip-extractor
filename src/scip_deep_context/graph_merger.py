"""Graph merger — merge multiple .graph.json files into a unified graph."""
from __future__ import annotations

import json
from typing import Any, List


class IndexHashMismatchError(Exception):
    """Raised when graphs have different scip_index_hash values (ADR-5)."""
    pass


def merge_graphs(graphs: List[dict]) -> dict:
    """Merge multiple graph dicts into a unified graph.

    - ADR-5: All graphs must share the same scip_index_hash
    - ADR-4: node 'layer' is converted to 'source_layers' dict
    - Nodes union by key; edges dedup by (from, to, type)
    - is_test takes OR across graphs

    Raises:
        IndexHashMismatchError: if any graph has a different scip_index_hash
        ValueError: if graphs list is empty
    """
    if not graphs:
        raise ValueError("graphs list must not be empty")

    # ADR-5: Validate all scip_index_hash values match
    hashes = [g.get("metadata", {}).get("scip_index_hash") for g in graphs]
    unique_hashes = set(h for h in hashes if h is not None)
    if len(unique_hashes) > 1:
        raise IndexHashMismatchError(
            f"Cannot merge graphs with different scip_index_hash values: "
            f"{sorted(unique_hashes)}"
        )

    # Collect metadata sources
    sources: List[dict] = []
    for g in graphs:
        meta = g.get("metadata", {})
        existing_sources = meta.get("sources")
        if existing_sources:
            # Incremental merge: already-merged graph has sources list
            sources.extend(existing_sources)
        else:
            sources.append({
                "entry_symbol": meta.get("entry_symbol"),
                "context_file": meta.get("context_file"),
            })

    # Merge nodes — union by key, layer → source_layers (ADR-4), is_test OR
    merged_nodes: dict[str, dict] = {}
    for g in graphs:
        context_file = g.get("metadata", {}).get("context_file", "")
        for key, node in g.get("nodes", {}).items():
            if key not in merged_nodes:
                merged_nodes[key] = {
                    "file": node.get("file", ""),
                    "lines": node.get("lines", []),
                    "is_test": node.get("is_test", False),
                    "is_partial": node.get("is_partial", False),
                    "source_layers": {},
                }
            else:
                # is_test takes OR
                if node.get("is_test", False):
                    merged_nodes[key]["is_test"] = True
                # is_partial takes OR (REQ-08)
                if node.get("is_partial", False):
                    merged_nodes[key]["is_partial"] = True

            # ADR-4: layer → source_layers
            layer_val = node.get("layer")
            if layer_val is not None:
                # Single graph: use context_file as key
                if context_file:
                    merged_nodes[key]["source_layers"][context_file] = layer_val
            else:
                # Already-merged graph: expand source_layers
                for ctx_file, layer in node.get("source_layers", {}).items():
                    merged_nodes[key]["source_layers"][ctx_file] = layer

    # Merge edges — dedup by (from, to, type), deterministic ordering
    seen_edges: set[tuple[str, str, str]] = set()
    merged_edges: list[dict] = []
    for g in graphs:
        for edge in g.get("edges", []):
            edge_key = (edge["from"], edge["to"], edge["type"])
            if edge_key not in seen_edges:
                seen_edges.add(edge_key)
                merged_edges.append({
                    "from": edge["from"],
                    "to": edge["to"],
                    "type": edge["type"],
                })
    merged_edges.sort(key=lambda e: (e["from"], e["to"], e["type"]))

    merged_meta: dict[str, Any] = {
        "scip_index_hash": hashes[0] if hashes else None,
        "sources": sources,
    }

    return {
        "metadata": merged_meta,
        "nodes": merged_nodes,
        "edges": merged_edges,
    }


def load_graph(path: str) -> dict:
    """Load a graph JSON file."""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_graph(graph: dict, path: str) -> None:
    """Save a graph dict to a JSON file."""
    with open(path, "w", encoding="utf-8") as f:
        json.dump(graph, f, indent=2, ensure_ascii=False)
