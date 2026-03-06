"""Test extractor — find test symbols in the symbol table for batch extract."""
from __future__ import annotations

import fnmatch
import os
from typing import Dict, List, Optional, Tuple

from scip_deep_context.models import SymbolInfo, SymbolRole


_TEST_FILE_PATTERNS = ("test_", "_test.", ".test.", "tests/", "test/")


def _is_test_file(file_uri: str) -> bool:
    """Check if a file path matches common test file patterns."""
    for pattern in _TEST_FILE_PATTERNS:
        if pattern in file_uri:
            return True
    return False


def _is_test_symbol(info: SymbolInfo, file_uri: str) -> bool:
    """Check if a symbol is a test symbol (by role or file path)."""
    for defn in info.definitions:
        if defn.roles & SymbolRole.TEST:
            return True
    return _is_test_file(file_uri)


def extract_test_symbols(
    symbol_table: Dict[str, SymbolInfo],
    file_pattern: Optional[str] = None,
    method_pattern: Optional[str] = None,
) -> List[Tuple[str, str, int]]:
    """Extract test symbols from the symbol table.

    Args:
        symbol_table: The full symbol table.
        file_pattern: Glob pattern to match test file names (basename).
        method_pattern: Glob pattern to match test method/function names.

    Returns:
        List of (symbol_key, file_uri, line) tuples for matched test symbols.
    """
    results: List[Tuple[str, str, int]] = []

    for sym_key, info in symbol_table.items():
        if not info.definitions:
            continue

        # Skip local symbols
        if sym_key.startswith("local "):
            continue

        defn = info.definitions[0]
        file_uri = defn.file_uri

        # File pattern filter
        if file_pattern:
            basename = os.path.basename(file_uri)
            if not fnmatch.fnmatch(basename, file_pattern):
                continue

        # Must be a test symbol
        if not _is_test_symbol(info, file_uri):
            continue

        # Method pattern filter (match against the symbol key or its descriptor)
        if method_pattern:
            if not fnmatch.fnmatch(sym_key, method_pattern):
                continue

        results.append((sym_key, file_uri, defn.line))

    # Sort by file, then line for deterministic output
    results.sort(key=lambda x: (x[1], x[2]))
    return results
