from __future__ import annotations

import hashlib
import json
from typing import List, Optional

import yaml

from scip_deep_context.models import CodeBlock, GraphEdge, OutputMetadata, TraversalResult


def _extract_descriptor(symbol: str) -> str:
    """Strip SCIP metadata prefix, return only the descriptor part."""
    if symbol.startswith("local "):
        return symbol
    parts = symbol.split(" ", 4)
    if len(parts) >= 5:
        return parts[4]
    if len(parts) == 2:
        return parts[1]
    return symbol


def _compute_scip_hash(scip_file: str) -> str:
    """Compute SHA256 hash of the SCIP index file."""
    h = hashlib.sha256()
    with open(scip_file, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return f"sha256:{h.hexdigest()}"


_SCHEME_TO_LANGUAGE: dict[str, str] = {
    "scip-python": "python",
    "scip-go": "go",
    "scip-typescript": "typescript",
    "scip-java": "java",
    "scip-ruby": "ruby",
    "scip-rust": "rust",
}


_EXT_TO_LANGUAGE: dict[str, str] = {
    ".py": "python",
    ".go": "go",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".js": "javascript",
    ".jsx": "javascript",
    ".java": "java",
    ".rb": "ruby",
    ".rs": "rust",
}


def _detect_language(symbol: str, file_path: str = "") -> str:
    """Detect programming language from SCIP symbol scheme, with file extension fallback."""
    if symbol.startswith("local "):
        return ""
    scheme = symbol.split(" ", 1)[0]
    lang = _SCHEME_TO_LANGUAGE.get(scheme, "")
    if lang:
        return lang
    # Valid SCIP format (>= 5 space-separated parts) with unknown scheme
    if len(symbol.split(" ")) >= 5:
        return ""
    # Not SCIP format — fallback to file extension
    if file_path:
        import os
        _, ext = os.path.splitext(file_path)
        return _EXT_TO_LANGUAGE.get(ext, "")
    return ""


def _remove_contained_blocks(
    blocks: list[CodeBlock],
    *,
    dedup_enabled: bool = True,
) -> list[CodeBlock]:
    """Post-processing：移除行範圍被其他 block 完全包含的 block。"""
    if not dedup_enabled:
        return blocks

    by_file: dict[str, list[CodeBlock]] = {}
    for block in blocks:
        by_file.setdefault(block.file_path, []).append(block)

    contained: set[str] = set()

    for file_path, file_blocks in by_file.items():
        file_blocks.sort(key=lambda b: (b.start_line, -b.end_line))

        for i, outer in enumerate(file_blocks):
            for j in range(i + 1, len(file_blocks)):
                inner = file_blocks[j]
                if inner.end_line <= outer.end_line:
                    if inner.symbol != outer.symbol:
                        contained.add(inner.symbol)

    return [b for b in blocks if b.symbol not in contained]


def _collect_all_blocks(result: TraversalResult) -> list[CodeBlock]:
    """Collect all CodeBlocks from all layers, sorted by depth."""
    all_blocks: list[CodeBlock] = []
    for depth in sorted(result.layers.keys()):
        all_blocks.extend(result.layers[depth])
    return all_blocks


def format_output(
    result: TraversalResult,
    max_nodes: int,
    *,
    dedup: bool = True,
    raw_symbols: bool = False,
) -> str:
    all_blocks = _collect_all_blocks(result)

    filtered_blocks = _remove_contained_blocks(all_blocks, dedup_enabled=dedup)
    filtered_symbols = {b.symbol for b in filtered_blocks}

    # Only override collected_nodes when dedup actually removed blocks
    rendered_count = len(filtered_blocks) if len(filtered_blocks) != len(all_blocks) else None

    meta = _build_metadata(result, max_nodes, rendered_count=rendered_count)
    yaml_part = _render_yaml_frontmatter(meta)
    md_part = _render_markdown(result, kept_symbols=filtered_symbols, raw_symbols=raw_symbols)
    return yaml_part + md_part


def format_graph_json(
    result: TraversalResult,
    entry_file: str,
    entry_line: int,
    entry_symbol: str,
    scip_file: str,
    context_file: Optional[str] = None,
    *,
    raw_symbols: bool = False,
    dedup: bool = True,
) -> str:
    """Format traversal result as a graph JSON string."""
    scip_hash = _compute_scip_hash(scip_file)

    metadata = {
        "scip_index_hash": scip_hash,
        "entry_file": entry_file,
        "entry_line": entry_line,
        "entry_symbol": entry_symbol if raw_symbols else _extract_descriptor(entry_symbol),
        "context_file": context_file,
    }

    # REQ-02: Apply containment dedup (same logic as Markdown output)
    all_blocks = _collect_all_blocks(result)
    filtered_blocks = _remove_contained_blocks(all_blocks, dedup_enabled=dedup)
    kept_symbols = {b.symbol for b in filtered_blocks}

    # Build nodes dict — filtered by kept_symbols
    nodes: dict = {}
    for full_sym, meta in result.node_metadata.items():
        if full_sym not in kept_symbols:
            continue
        key = full_sym if raw_symbols else _extract_descriptor(full_sym)
        nodes[key] = {
            "file": meta["file"],
            "lines": meta["lines"],
            "layer": meta["layer"],
            "is_test": meta["is_test"],
            "is_partial": meta.get("is_partial", False),
        }

    # Build edges list with dedup by (from, to, type)
    edges: list = []
    seen_edges: set = set()
    for edge in result.edges:
        # REQ-02: skip edges involving removed nodes
        if edge.from_symbol not in kept_symbols or edge.to_symbol not in kept_symbols:
            continue
        from_key = edge.from_symbol if raw_symbols else _extract_descriptor(edge.from_symbol)
        to_key = edge.to_symbol if raw_symbols else _extract_descriptor(edge.to_symbol)
        edge_tuple = (from_key, to_key, edge.edge_type)
        if edge_tuple not in seen_edges:
            seen_edges.add(edge_tuple)
            edges.append({
                "from": from_key,
                "to": to_key,
                "type": edge.edge_type,
            })

    # Deterministic ordering (BDD C-07)
    edges.sort(key=lambda e: (e["from"], e["to"], e["type"]))

    graph = {
        "metadata": metadata,
        "nodes": nodes,
        "edges": edges,
    }

    return json.dumps(graph, indent=2, ensure_ascii=False)


def _build_metadata(
    result: TraversalResult,
    max_nodes: int,
    *,
    rendered_count: int | None = None,
) -> OutputMetadata:
    return OutputMetadata(
        duration_sec=result.duration_sec,
        collected_nodes=rendered_count if rendered_count is not None else result.collected_nodes,
        max_nodes=max_nodes,
        is_truncated=result.is_truncated,
        truncation_reasons=list(result.truncation_reasons),
        alerts_count=len(result.broken_links),
    )


def _render_yaml_frontmatter(meta: OutputMetadata) -> str:
    data = {
        "duration_sec": meta.duration_sec,
        "collected_nodes": meta.collected_nodes,
        "max_nodes": meta.max_nodes,
        "is_truncated": meta.is_truncated,
        "truncation_reasons": meta.truncation_reasons,
        "alerts_count": meta.alerts_count,
    }
    return "---\n" + yaml.dump(data, default_flow_style=False, sort_keys=False) + "---\n"


def _render_markdown(
    result: TraversalResult,
    *,
    kept_symbols: set[str] | None = None,
    raw_symbols: bool = False,
) -> str:
    parts: List[str] = []

    for depth in sorted(result.layers.keys()):
        blocks = result.layers[depth]
        if kept_symbols is not None:
            blocks = [b for b in blocks if b.symbol in kept_symbols]
        if not blocks:
            continue
        if depth == 0:
            parts.append(f"\n## Layer 0 — Entry Point\n")
        else:
            parts.append(f"\n## Layer {depth} — Depth {depth}\n")
        for block in blocks:
            label = f"`{block.file_path}` L{block.start_line}-L{block.end_line}"
            if block.is_partial:
                label += " *(partial extraction)*"
            if block.is_file_missing:
                label += " *(file missing)*"
            header = block.symbol if raw_symbols else _extract_descriptor(block.symbol)
            parts.append(f"\n### {header}\n")
            parts.append(f"{label}\n")
            lang = _detect_language(block.symbol, block.file_path)
            parts.append(f"\n```{lang}\n{block.code}\n```\n")

    if result.broken_links:
        parts.append("\n## Alerts\n")
        for link in result.broken_links:
            parts.append(
                f"- **{link.reason}**: `{link.file_path}` L{link.line}"
            )
            if link.code_snippet:
                parts.append(f" — `{link.code_snippet}`")
            parts.append("\n")

    return "".join(parts)
