"""BFS traverser — breadth-first symbol graph traversal engine."""
from __future__ import annotations

from collections import deque
from typing import Dict, List, Optional

from scip_deep_context.broken_link_detector import detect_broken_link
from scip_deep_context.clock import Clock, RealClock
from scip_deep_context.models import (
    CodeBlock,
    GraphEdge,
    Occurrence,
    SymbolInfo,
    SymbolRole,
    TraversalResult,
)
from scip_deep_context.symbol_filter import SymbolFilter, is_field_like, is_function_like
from scip_deep_context.source_extractor import FileReader, RealFileReader, extract_source


def _find_children_in_block(
    block: CodeBlock,
    symbol_table: Dict[str, SymbolInfo],
    current_symbol: str,
) -> List[str]:
    """Find reference symbols whose occurrences fall within *block*'s range."""
    if not block.file_path or block.is_file_missing:
        return []

    start_line_0 = block.start_line - 1  # convert to 0-based
    end_line_0 = block.end_line - 1

    children = []
    for sym, info in symbol_table.items():
        if sym == current_symbol:
            continue
        for ref in info.references:
            if (
                ref.file_uri == block.file_path
                and start_line_0 <= ref.line <= end_line_0
            ):
                children.append(sym)
                break  # one match per symbol is enough
    return children


def _expand_interfaces(
    sym: str,
    symbol_table: Dict[str, SymbolInfo],
    max_impls: int,
) -> List[str]:
    """If *sym* has implementation relationships, return up to *max_impls* of them."""
    info = symbol_table.get(sym)
    if info is None:
        return []
    impls = [r.symbol for r in info.relationships if r.is_implementation]
    return impls[:max_impls]


_TEST_FILE_PATTERNS = ("test_", "_test.", ".test.", "tests/", "test/")


def _is_test_node(
    symbol_info: Optional[SymbolInfo],
    file_path: str,
) -> bool:
    """Determine if a symbol is a test node.

    Priority: SymbolRole.TEST (0x20) > file path pattern fallback.
    """
    if symbol_info is not None:
        for defn in symbol_info.definitions:
            if defn.roles & SymbolRole.TEST:
                return True
    for pattern in _TEST_FILE_PATTERNS:
        if pattern in file_path:
            return True
    return False


def _build_node_meta(
    block: CodeBlock,
    layer: int,
    symbol_info: Optional[SymbolInfo],
) -> dict:
    """Build node metadata dict for graph JSON output."""
    return {
        "file": block.file_path,
        "lines": [block.start_line, block.end_line],
        "layer": layer,
        "is_test": _is_test_node(symbol_info, block.file_path),
        "is_partial": block.is_partial,
    }


def traverse(
    entry_symbol: str,
    symbol_table: Dict[str, SymbolInfo],
    symbol_filter: SymbolFilter,
    project_root: str,
    max_nodes: int,
    timeout: float,
    clock: Optional[Clock] = None,
    file_reader: Optional[FileReader] = None,
    max_interface_impls: int = 3,
    include_fields: bool = False,
) -> TraversalResult:
    """BFS traversal engine."""
    if clock is None:
        clock = RealClock()
    if file_reader is None:
        file_reader = RealFileReader()

    result = TraversalResult()
    visited = {entry_symbol}
    queue: deque = deque()
    collected = 0
    start_time = clock.now()

    # Layer 0: entry point
    entry_info = symbol_table.get(entry_symbol)
    if entry_info is not None:
        entry_block = extract_source(
            entry_symbol, entry_info, project_root, file_reader
        )
        result.layers[0] = [entry_block]
        collected = 1
        queue.append((entry_symbol, 0))
        # Record entry node metadata
        result.node_metadata[entry_symbol] = _build_node_meta(entry_block, 0, entry_info)
    else:
        result.layers[0] = []

    while queue:
        # Dual guard
        elapsed = clock.now() - start_time
        reasons: List[str] = []
        if elapsed > timeout:
            reasons.append("timeout")
        if collected >= max_nodes:
            reasons.append("max_nodes")
        if reasons:
            result.is_truncated = True
            result.truncation_reasons = reasons
            break

        current_symbol, current_layer = queue.popleft()
        next_layer = current_layer + 1

        current_info = symbol_table.get(current_symbol)
        if current_info is None:
            continue

        # Get the code block for the current symbol to find children
        current_block = result.layers.get(current_layer, [])
        block_for_current = None
        for b in current_block:
            if b.symbol == current_symbol:
                block_for_current = b
                break

        if block_for_current is None:
            continue

        child_symbols = _find_children_in_block(
            block_for_current, symbol_table, current_symbol
        )

        for child_sym in child_symbols:
            # REQ-01/REQ-02: function-like filter (exclude fields by default)
            if not is_function_like(child_sym):
                if not (include_fields and is_field_like(child_sym)):
                    continue

            child_info = symbol_table.get(child_sym)

            # ① Filter check FIRST — external symbols are skipped entirely,
            # no edge recording, no broken link reporting
            def_uri = (
                child_info.definitions[0].file_uri
                if child_info and child_info.definitions
                else None
            )
            if not symbol_filter.is_internal(child_sym, def_uri):
                continue

            # ② ADR-3: Record reference edge regardless of visited status
            result.edges.append(
                GraphEdge(
                    from_symbol=current_symbol,
                    to_symbol=child_sym,
                    edge_type="reference",
                )
            )

            # ③ Dedup — already visited nodes get edge but don't re-enter queue
            if child_sym in visited:
                continue

            visited.add(child_sym)

            # Broken link detection (only for internal symbols)
            if child_info is not None and child_info.references:
                bl = detect_broken_link(child_info.references[0], symbol_table)
                if bl is not None:
                    result.broken_links.append(bl)

            # Interface expansion
            if child_info is not None:
                impls = _expand_interfaces(
                    child_sym, symbol_table, max_interface_impls
                )
                if child_info.relationships and not impls:
                    # Has relationships but no implementations — warning
                    from scip_deep_context.models import BrokenLink

                    result.broken_links.append(
                        BrokenLink(
                            file_path=child_info.definitions[0].file_uri
                            if child_info.definitions
                            else "",
                            line=child_info.definitions[0].line + 1
                            if child_info.definitions
                            else 0,
                            code_snippet="",
                            reason="no_implementation",
                        )
                    )

                for impl_sym in impls:
                    impl_info = symbol_table.get(impl_sym)
                    impl_def_uri = (
                        impl_info.definitions[0].file_uri
                        if impl_info and impl_info.definitions
                        else None
                    )
                    # ADR-3: Record implementation edge regardless of visited
                    if impl_info is not None and symbol_filter.is_internal(impl_sym, impl_def_uri):
                        result.edges.append(
                            GraphEdge(
                                from_symbol=child_sym,
                                to_symbol=impl_sym,
                                edge_type="implementation",
                            )
                        )

                    if impl_sym not in visited:
                        visited.add(impl_sym)
                        if impl_info is not None:
                            if symbol_filter.is_internal(impl_sym, impl_def_uri):
                                if collected >= max_nodes:
                                    break
                                impl_block = extract_source(
                                    impl_sym,
                                    impl_info,
                                    project_root,
                                    file_reader,
                                )
                                result.layers.setdefault(next_layer, []).append(
                                    impl_block
                                )
                                collected += 1
                                queue.append((impl_sym, next_layer))
                                # Record impl node metadata
                                result.node_metadata[impl_sym] = _build_node_meta(impl_block, next_layer, impl_info)

            if child_info is None:
                continue

            if collected >= max_nodes:
                break

            child_block = extract_source(
                child_sym, child_info, project_root, file_reader
            )
            result.layers.setdefault(next_layer, []).append(child_block)
            collected += 1
            queue.append((child_sym, next_layer))

            # Record child node metadata
            result.node_metadata[child_sym] = _build_node_meta(child_block, next_layer, child_info)

    if result.is_truncated:
        result.pending_symbols = [sym for sym, _layer in queue]

    # Sort blocks within each layer by symbol name
    for layer in result.layers:
        result.layers[layer] = sorted(
            result.layers[layer], key=lambda b: b.symbol
        )

    elapsed_total = clock.now() - start_time
    result.duration_sec = elapsed_total
    result.collected_nodes = collected

    return result
