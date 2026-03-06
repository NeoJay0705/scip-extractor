"""SCIP loader — load protobuf-binary SCIP index and build symbol table."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Dict, List

from scip_deep_context import scip_pb2
from scip_deep_context.models import (
    Occurrence,
    Relationship,
    SCIPLoadError,
    SymbolInfo,
    SymbolRole,
)

logger = logging.getLogger(__name__)


@dataclass
class SCIPDocument:
    relative_path: str
    occurrences: List[dict] = field(default_factory=list)
    symbols: List[dict] = field(default_factory=list)


@dataclass
class SCIPIndex:
    documents: List[SCIPDocument] = field(default_factory=list)
    metadata_version: str = "0.3.0"


def load_scip(scip_file_path: str) -> SCIPIndex:
    """Load a protobuf-binary SCIP index from *scip_file_path*.

    Raises SCIPLoadError when the file does not exist or is corrupted.
    """
    try:
        with open(scip_file_path, "rb") as f:
            raw = f.read()
    except FileNotFoundError:
        raise SCIPLoadError(f"SCIP file not found: {scip_file_path}")

    try:
        pb_index = scip_pb2.Index()
        pb_index.ParseFromString(raw)
    except Exception as exc:
        raise SCIPLoadError(f"Corrupted SCIP file: {scip_file_path}: {exc}")

    docs: List[SCIPDocument] = []
    expanded_3elem_count = 0
    for pb_doc in pb_index.documents:
        occurrences = []
        for occ in pb_doc.occurrences:
            r = list(occ.range)
            # Range: [start_line, start_char, end_char] or [start_line, start_char, end_line, end_char]
            enc = list(occ.enclosing_range) if occ.enclosing_range else None
            if enc and len(enc) == 4:
                enc_value = enc
            elif enc and len(enc) == 3:
                # 3-element [start_line, start_char, end_char] → same-line expansion
                enc_value = [enc[0], enc[1], enc[0], enc[2]]
                expanded_3elem_count += 1
                logger.debug("Expanded 3-element enclosing_range %s → %s for symbol %s",
                             enc, enc_value, occ.symbol)
            else:
                enc_value = None
            occurrences.append({
                "symbol": occ.symbol,
                "roles": occ.symbol_roles,
                "line": r[0] if r else 0,
                "character": r[1] if len(r) > 1 else 0,
                "enclosing_range": enc_value,
            })
        symbols = []
        for sym in pb_doc.symbols:
            rels = []
            for rel in sym.relationships:
                rels.append({
                    "symbol": rel.symbol,
                    "is_implementation": rel.is_implementation,
                })
            symbols.append({"symbol": sym.symbol, "relationships": rels})
        docs.append(SCIPDocument(
            relative_path=pb_doc.relative_path,
            occurrences=occurrences,
            symbols=symbols,
        ))

    if expanded_3elem_count > 0:
        logger.info("Expanded %d 3-element enclosing_range(s) to 4-element format",
                     expanded_3elem_count)
    return SCIPIndex(documents=docs, metadata_version="0.3.0")


def _parse_role(role_value: int) -> SymbolRole:
    """Convert an integer role value to SymbolRole flags."""
    result = SymbolRole(0)
    if role_value & SymbolRole.DEFINITION:
        result = result | SymbolRole.DEFINITION
    # Any of WriteAccess/ReadAccess/Import counts as reference
    if role_value & (SymbolRole.READ_ACCESS | SymbolRole.WRITE_ACCESS | SymbolRole.IMPORT):
        result = result | SymbolRole.READ_ACCESS
    return result


def build_symbol_table(index: SCIPIndex) -> Dict[str, SymbolInfo]:
    """Build a symbol lookup table from a SCIPIndex."""
    defs: Dict[str, List[Occurrence]] = {}
    refs: Dict[str, List[Occurrence]] = {}
    rels: Dict[str, List[Relationship]] = {}

    for doc in index.documents:
        file_uri = doc.relative_path

        for occ_raw in doc.occurrences:
            sym = occ_raw.get("symbol", "")
            if not sym:
                continue
            role_val = occ_raw.get("roles", 0)
            enc = occ_raw.get("enclosing_range")
            if enc and len(enc) == 4:
                enc_tuple = tuple(enc)
            elif enc and len(enc) == 3:
                enc_tuple = (enc[0], enc[1], enc[0], enc[2])
            else:
                enc_tuple = None

            is_definition = bool(role_val & 0x1)
            is_reference = bool(role_val & (0x2 | 0x4 | 0x8))

            roles = SymbolRole(0)
            if is_definition:
                roles = roles | SymbolRole.DEFINITION
            if is_reference:
                roles = roles | SymbolRole.READ_ACCESS

            occ = Occurrence(
                symbol=sym,
                line=occ_raw.get("line", 0),
                character=occ_raw.get("character", 0),
                roles=roles,
                file_uri=file_uri,
                enclosing_range=enc_tuple,
            )

            if is_definition:
                defs.setdefault(sym, []).append(occ)
            if is_reference:
                refs.setdefault(sym, []).append(occ)

        for sym_raw in doc.symbols:
            sym = sym_raw.get("symbol", "")
            if not sym:
                continue
            for rel_raw in sym_raw.get("relationships", []):
                rel = Relationship(
                    symbol=rel_raw.get("symbol", ""),
                    is_implementation=rel_raw.get("is_implementation", False),
                )
                rels.setdefault(sym, []).append(rel)

    all_syms = set(defs) | set(refs) | set(rels)
    table: Dict[str, SymbolInfo] = {}
    for sym in all_syms:
        table[sym] = SymbolInfo(
            symbol=sym,
            definitions=defs.get(sym, []),
            references=refs.get(sym, []),
            relationships=rels.get(sym, []),
        )
    return table
