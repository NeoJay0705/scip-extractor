from __future__ import annotations

from typing import Dict, Optional

from scip_deep_context.models import BrokenLink, Occurrence, SymbolInfo


def detect_broken_link(
    occurrence: Occurrence,
    symbol_table: Dict[str, SymbolInfo],
) -> Optional[BrokenLink]:
    """Return a BrokenLink if the occurrence cannot be resolved, else None."""
    if not occurrence.symbol:
        return BrokenLink(
            file_path=occurrence.file_uri,
            line=occurrence.line + 1,
            code_snippet="",
            reason="unresolved",
        )

    info = symbol_table.get(occurrence.symbol)
    if info is None or not info.definitions:
        return BrokenLink(
            file_path=occurrence.file_uri,
            line=occurrence.line + 1,
            code_snippet="",
            reason="no_definition",
        )

    return None
