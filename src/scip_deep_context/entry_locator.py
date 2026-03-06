"""Entry locator — find the leftmost reference symbol at a given line."""
from __future__ import annotations

from typing import Dict

from scip_deep_context.models import NoReferenceFoundError, SymbolInfo, SymbolRole


def locate_entry_symbol(
    symbol_table: Dict[str, SymbolInfo],
    entry_file: str,
    entry_line: int,
) -> str:
    """Find the leftmost Definition or Reference Occurrence at *entry_line* (1-based).

    Prefers Definitions (e.g. when pointing at a def/class line with type annotations);
    falls back to References.
    Raises NoReferenceFoundError when nothing is found.
    """
    target_line = entry_line - 1  # convert to 0-based

    ref_candidates = []
    def_candidates = []
    for info in symbol_table.values():
        for ref in info.references:
            if ref.file_uri == entry_file and ref.line == target_line and ref.symbol:
                ref_candidates.append(ref)
        for defn in info.definitions:
            if defn.file_uri == entry_file and defn.line == target_line and defn.symbol:
                def_candidates.append(defn)

    candidates = def_candidates if def_candidates else ref_candidates

    if not candidates:
        raise NoReferenceFoundError(
            f"No reference found at {entry_file}:{entry_line}"
        )

    candidates.sort(key=lambda occ: occ.character)
    return candidates[0].symbol
