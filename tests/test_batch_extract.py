from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from scip_deep_context.bfs_traverser import traverse
from scip_deep_context.cli import _batch_extract
from scip_deep_context.models import BrokenLink, CLIArgs, TraversalResult
from scip_deep_context.scip_loader import build_symbol_table, load_scip
from scip_deep_context.symbol_filter import SymbolFilter
from scip_deep_context.test_extractor import extract_test_symbols


def _make_broken_link(reason: str = "no_definition") -> BrokenLink:
    return BrokenLink(file_path="test.py", line=1, code_snippet="x", reason=reason)


def _make_result(broken_links: list[BrokenLink] | None = None) -> TraversalResult:
    return TraversalResult(broken_links=broken_links or [])


def _make_cli_args(**overrides) -> CLIArgs:
    defaults = dict(
        scip_file="index.scip",
        project_root=".",
        entry_file=None,
        entry_line=None,
        project_modules=[],
        max_nodes=10,
        timeout=3.0,
        exclude_patterns=[],
        dedup=True,
        raw_symbols=False,
        graph_output=None,
        test_file_pattern="test_*.py",
        test_method_pattern=None,
        include_fields=False,
    )
    defaults.update(overrides)
    return CLIArgs(**defaults)


@patch("scip_deep_context.cli.format_output", return_value="mock output")
@patch("scip_deep_context.cli.traverse")
@patch("scip_deep_context.test_extractor.extract_test_symbols")
@patch("scip_deep_context.cli.build_symbol_table", return_value={})
@patch("scip_deep_context.cli.load_scip", return_value=MagicMock())
def test_batch_no_broken_links_returns_0(
    _mock_load_scip: MagicMock,
    _mock_build_symbol_table: MagicMock,
    mock_extract_test_symbols: MagicMock,
    mock_traverse: MagicMock,
    _mock_format_output: MagicMock,
    capsys: pytest.CaptureFixture[str],
) -> None:
    mock_extract_test_symbols.return_value = [("sym1", "tests/a_test.py", 0), ("sym2", "tests/b_test.py", 1)]
    mock_traverse.side_effect = [_make_result(), _make_result()]

    exit_code = _batch_extract(_make_cli_args())
    captured = capsys.readouterr()

    assert exit_code == 0
    assert mock_traverse.call_count == 2
    assert captured.out != ""


@patch("scip_deep_context.cli.format_output", return_value="mock output")
@patch("scip_deep_context.cli.traverse")
@patch("scip_deep_context.test_extractor.extract_test_symbols")
@patch("scip_deep_context.cli.build_symbol_table", return_value={})
@patch("scip_deep_context.cli.load_scip", return_value=MagicMock())
def test_batch_first_has_broken_links_returns_1(
    _mock_load_scip: MagicMock,
    _mock_build_symbol_table: MagicMock,
    mock_extract_test_symbols: MagicMock,
    mock_traverse: MagicMock,
    _mock_format_output: MagicMock,
    capsys: pytest.CaptureFixture[str],
) -> None:
    mock_extract_test_symbols.return_value = [("sym1", "tests/a_test.py", 0), ("sym2", "tests/b_test.py", 1)]
    mock_traverse.side_effect = [_make_result([_make_broken_link()]), _make_result()]

    exit_code = _batch_extract(_make_cli_args())
    captured = capsys.readouterr()

    assert exit_code == 1
    assert mock_traverse.call_count == 2
    assert captured.out != ""


@patch("scip_deep_context.cli.format_output", return_value="mock output")
@patch("scip_deep_context.cli.traverse")
@patch("scip_deep_context.test_extractor.extract_test_symbols")
@patch("scip_deep_context.cli.build_symbol_table", return_value={})
@patch("scip_deep_context.cli.load_scip", return_value=MagicMock())
def test_batch_last_has_broken_links_returns_1(
    _mock_load_scip: MagicMock,
    _mock_build_symbol_table: MagicMock,
    mock_extract_test_symbols: MagicMock,
    mock_traverse: MagicMock,
    _mock_format_output: MagicMock,
    capsys: pytest.CaptureFixture[str],
) -> None:
    mock_extract_test_symbols.return_value = [("sym1", "tests/a_test.py", 0), ("sym2", "tests/b_test.py", 1)]
    mock_traverse.side_effect = [_make_result(), _make_result([_make_broken_link()])]

    exit_code = _batch_extract(_make_cli_args())
    captured = capsys.readouterr()

    assert exit_code == 1
    assert mock_traverse.call_count == 2
    assert captured.out != ""


@patch("scip_deep_context.cli.format_output", return_value="mock output")
@patch("scip_deep_context.cli.traverse")
@patch("scip_deep_context.test_extractor.extract_test_symbols")
@patch("scip_deep_context.cli.build_symbol_table", return_value={})
@patch("scip_deep_context.cli.load_scip", return_value=MagicMock())
def test_batch_all_have_broken_links_returns_1(
    _mock_load_scip: MagicMock,
    _mock_build_symbol_table: MagicMock,
    mock_extract_test_symbols: MagicMock,
    mock_traverse: MagicMock,
    _mock_format_output: MagicMock,
    capsys: pytest.CaptureFixture[str],
) -> None:
    mock_extract_test_symbols.return_value = [("sym1", "tests/a_test.py", 0), ("sym2", "tests/b_test.py", 1)]
    mock_traverse.side_effect = [
        _make_result([_make_broken_link("no_definition")]),
        _make_result([_make_broken_link("no_implementation")]),
    ]

    exit_code = _batch_extract(_make_cli_args())
    captured = capsys.readouterr()

    assert exit_code == 1
    assert mock_traverse.call_count == 2
    assert captured.out != ""


def test_batch_integration_with_real_scip_index(capsys: pytest.CaptureFixture[str]) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    scip_file = repo_root / "index.scip"
    if not scip_file.exists():
        pytest.skip("index.scip not found in repository root")

    args = _make_cli_args(
        scip_file=str(scip_file),
        project_root=str(repo_root),
        test_file_pattern="test_*.py",
        test_method_pattern=None,
    )

    index = load_scip(args.scip_file)
    symbol_table = build_symbol_table(index)
    test_symbols = extract_test_symbols(
        symbol_table,
        file_pattern=args.test_file_pattern,
        method_pattern=args.test_method_pattern,
    )
    if not test_symbols:
        pytest.skip("No test symbols in index.scip for integration test")

    sf = SymbolFilter(args.project_modules, args.project_root, args.exclude_patterns)
    has_broken_links = False
    for sym_key, _file_uri, _line in test_symbols:
        if traverse(sym_key, symbol_table, sf, args.project_root, args.max_nodes, args.timeout, include_fields=args.include_fields).broken_links:
            has_broken_links = True
            break

    if not has_broken_links:
        pytest.skip("Current index.scip has no test symbol producing broken links")

    exit_code = _batch_extract(args)
    captured = capsys.readouterr()
    assert exit_code == 1
    assert captured.out != ""
