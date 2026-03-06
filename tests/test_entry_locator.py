from __future__ import annotations

from typing import Dict, List

import pytest

from scip_deep_context.entry_locator import locate_entry_symbol
from scip_deep_context.models import (
    NoReferenceFoundError,
    Occurrence,
    SymbolInfo,
    SymbolRole,
)


def _occ(
    symbol: str,
    line: int,
    character: int,
    *,
    file_uri: str = "app.py",
    is_def: bool = False,
) -> Occurrence:
    roles = SymbolRole.DEFINITION if is_def else SymbolRole.READ_ACCESS
    return Occurrence(
        symbol=symbol,
        line=line,
        character=character,
        roles=roles,
        file_uri=file_uri,
    )


def _make_symbol_table(data: Dict[str, List[Occurrence]]) -> Dict[str, SymbolInfo]:
    table: Dict[str, SymbolInfo] = {}
    for symbol, occs in data.items():
        defs = [o for o in occs if o.roles & SymbolRole.DEFINITION]
        refs = [o for o in occs if not (o.roles & SymbolRole.DEFINITION)]
        table[symbol] = SymbolInfo(
            symbol=symbol,
            definitions=defs,
            references=refs,
            relationships=[],
        )
    return table


def test_local_plus_function_returns_function() -> None:
    table = _make_symbol_table(
        {
            "local 16": [_occ("local 16", line=9, character=0)],
            "pkg mod foo().": [_occ("pkg mod foo().", line=9, character=4)],
        }
    )

    result = locate_entry_symbol(table, "app.py", 10)
    assert result == "pkg mod foo()."


def test_local_only_raises_local_error() -> None:
    table = _make_symbol_table(
        {
            "local 16": [_occ("local 16", line=9, character=2)],
        }
    )

    with pytest.raises(NoReferenceFoundError) as exc:
        locate_entry_symbol(table, "app.py", 10)

    message = str(exc.value)
    assert "Only local symbols found" in message
    assert "excluded from entry point selection" in message


def test_def_line_unchanged() -> None:
    table = _make_symbol_table(
        {
            "pkg mod bar().": [_occ("pkg mod bar().", line=20, character=0, is_def=True)],
            "local 7": [_occ("local 7", line=20, character=2, is_def=True)],
        }
    )

    result = locate_entry_symbol(table, "app.py", 21)
    assert result == "pkg mod bar()."


def test_local_filtered_without_symbol_filter() -> None:
    table = _make_symbol_table(
        {
            "local 8": [_occ("local 8", line=14, character=0)],
            "pkg mod call().": [_occ("pkg mod call().", line=14, character=6)],
        }
    )

    result = locate_entry_symbol(table, "app.py", 15)
    assert result == "pkg mod call()."


def test_multiple_locals_all_filtered() -> None:
    table = _make_symbol_table(
        {
            "local 1": [_occ("local 1", line=30, character=1)],
            "local 2": [_occ("local 2", line=30, character=5)],
        }
    )

    with pytest.raises(NoReferenceFoundError) as exc:
        locate_entry_symbol(table, "app.py", 31)

    assert "Only local symbols found" in str(exc.value)


def test_no_symbol_at_line_original_error() -> None:
    table = _make_symbol_table(
        {
            "pkg mod baz().": [_occ("pkg mod baz().", line=40, character=0)],
        }
    )

    with pytest.raises(NoReferenceFoundError) as exc:
        locate_entry_symbol(table, "app.py", 99)

    message = str(exc.value)
    assert message == "No reference found at app.py:99"
    assert "local symbols" not in message


def test_local_def_only_raises_local_error() -> None:
    """Local definitions (is_def=True) at target line without non-local symbols."""
    table = _make_symbol_table(
        {
            "local 5": [_occ("local 5", line=25, character=0, is_def=True)],
        }
    )

    with pytest.raises(NoReferenceFoundError) as exc:
        locate_entry_symbol(table, "app.py", 26)

    assert "Only local symbols found" in str(exc.value)


def test_leftmost_selection() -> None:
    table = _make_symbol_table(
        {
            "pkg mod first().": [_occ("pkg mod first().", line=49, character=1)],
            "pkg mod second().": [_occ("pkg mod second().", line=49, character=8)],
        }
    )

    result = locate_entry_symbol(table, "app.py", 50)
    assert result == "pkg mod first()."
