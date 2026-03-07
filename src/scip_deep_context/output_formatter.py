from __future__ import annotations

import hashlib
import json
from typing import List, Optional

import yaml

from scip_deep_context.models import CodeBlock, GraphEdge, OutputMetadata, TraversalResult
from scip_deep_context.source_extractor import read_source_by_range
from scip_deep_context.symbol_filter import match_module_patterns, parse_package


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
    output_modules: Optional[list[str]] = None,
    output_symbol_prefix: Optional[list[str]] = None,
) -> str:
    all_blocks = _collect_all_blocks(result)

    deduped_blocks = _remove_contained_blocks(all_blocks, dedup_enabled=dedup)
    deduped_symbols = {b.symbol for b in deduped_blocks}

    # Only override collected_nodes when dedup actually removed blocks
    rendered_count = len(deduped_blocks) if len(deduped_blocks) != len(all_blocks) else None

    filtered_blocks = deduped_blocks
    if output_modules:
        filtered_blocks = [
            block for block in filtered_blocks
            if _matches_output_modules(block.symbol, output_modules)
        ]
    if output_symbol_prefix:
        filtered_blocks = [
            block for block in filtered_blocks
            if _matches_output_symbol_prefix(block.symbol, output_symbol_prefix)
        ]

    has_output_filter = bool(output_modules) or bool(output_symbol_prefix)
    rendered_nodes: Optional[int] = len(filtered_blocks) if has_output_filter else None
    filtered_symbols = {b.symbol for b in filtered_blocks}

    meta = _build_metadata(
        result,
        max_nodes,
        rendered_count=rendered_count,
        rendered_nodes=rendered_nodes,
    )
    yaml_part = _render_yaml_frontmatter(meta)
    summary_part = _render_summary(result, deduped_symbols, raw_symbols=raw_symbols)
    md_part = _render_markdown(result, kept_symbols=filtered_symbols, raw_symbols=raw_symbols)
    return yaml_part + summary_part + md_part


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
    rendered_nodes: int | None = None,
) -> OutputMetadata:
    return OutputMetadata(
        duration_sec=result.duration_sec,
        collected_nodes=rendered_count if rendered_count is not None else result.collected_nodes,
        max_nodes=max_nodes,
        is_truncated=result.is_truncated,
        truncation_reasons=list(result.truncation_reasons),
        alerts_count=len(result.broken_links),
        rendered_nodes=rendered_nodes,
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
    if meta.rendered_nodes is not None:
        data["rendered_nodes"] = meta.rendered_nodes
    return "---\n" + yaml.dump(data, default_flow_style=False, sort_keys=False) + "---\n"


def _matches_output_modules(symbol: str, output_modules: list[str]) -> bool:
    pkg = parse_package(symbol)
    if not pkg:
        return False
    return match_module_patterns(pkg, output_modules)


def _matches_output_symbol_prefix(symbol: str, output_symbol_prefix: list[str]) -> bool:
    """Check if a symbol's descriptor starts with any of the given prefixes."""
    if not output_symbol_prefix:
        return True
    descriptor = _extract_descriptor(symbol)
    return any(descriptor.startswith(prefix) for prefix in output_symbol_prefix)


def _render_summary(
    result: TraversalResult,
    kept_symbols: set[str],
    *,
    raw_symbols: bool = False,
) -> str:
    parts: list[str] = ["\n## Summary\n"]

    module_counts: dict[str, int] = {}
    for symbol in sorted(kept_symbols):
        pkg = parse_package(symbol)
        if not pkg:
            continue
        module_counts[pkg] = module_counts.get(pkg, 0) + 1

    parts.append("\n### Modules\n")
    if module_counts:
        for module in sorted(module_counts):
            parts.append(f"- `{module}`: {module_counts[module]}\n")
    else:
        parts.append("- (none)\n")

    layer_counts: dict[int, int] = {}
    for layer in sorted(result.layers.keys()):
        count = sum(1 for block in result.layers[layer] if block.symbol in kept_symbols)
        layer_counts[layer] = count

    parts.append("\n### Layer Distribution\n")
    for layer in sorted(layer_counts):
        if layer_counts[layer] == 0:
            continue
        parts.append(f"- Layer {layer}: {layer_counts[layer]}\n")

    if result.pending_symbols:
        parts.append("\n### Truncated Branches\n")
        unique_pending: list[str] = []
        seen: set[str] = set()
        for symbol in result.pending_symbols:
            if symbol in seen:
                continue
            seen.add(symbol)
            unique_pending.append(symbol)
        display = unique_pending[:10]
        for symbol in display:
            label = symbol if raw_symbols else _extract_descriptor(symbol)
            parts.append(f"- `{label}`\n")
        if len(unique_pending) > 10:
            parts.append(f"- ... and {len(unique_pending) - 10} more\n")

    return "".join(parts)


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


def format_query_markdown(
    query_result: dict,
    query_type: str,
    entry_node: str,
    project_root: str,
) -> str:
    nodes = query_result.get("nodes", {})
    warnings = query_result.get("warnings", [])
    truncated_branches = query_result.get("truncated_branches", [])
    data = {
        "query_type": query_type,
        "entry_node": entry_node,
        "result_nodes": len(nodes),
        "is_truncated": bool(query_result.get("is_truncated", False)),
    }
    if warnings:
        data["warnings"] = warnings

    parts: list[str] = ["---\n", yaml.dump(data, default_flow_style=False, sort_keys=False), "---\n"]
    if warnings:
        parts.append("\n")
        for warning in warnings:
            parts.append(f"> ⚠️ Warning: {warning}\n")

    if truncated_branches:
        parts.append("\n### Truncated Branches\n")
        for branch in truncated_branches[:10]:
            parts.append(f"- `{branch}`\n")
        if len(truncated_branches) > 10:
            parts.append(f"- ... and {len(truncated_branches) - 10} more\n")

    parts.append("\n## Query Result\n")
    for symbol in sorted(nodes.keys()):
        node_meta = nodes[symbol]
        file_path = node_meta.get("file", "")
        lines = node_meta.get("lines", [0, 0])
        start_line = int(lines[0]) if len(lines) > 0 else 0
        end_line = int(lines[1]) if len(lines) > 1 else start_line
        source = read_source_by_range(project_root, file_path, start_line, end_line)
        parts.append(f"\n### {symbol}\n")
        parts.append(f"`{file_path}` L{start_line}-L{end_line}\n")
        lang = _detect_language(symbol, file_path)
        parts.append(f"\n```{lang}\n{source}\n```\n")
    return "".join(parts)
