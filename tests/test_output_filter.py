from __future__ import annotations

import json

import yaml

from scip_deep_context.cli import parse_args
from scip_deep_context.models import CodeBlock, GraphEdge, TraversalResult
from scip_deep_context.output_formatter import (
    _matches_output_modules,
    _matches_output_symbol_prefix,
    format_graph_json,
    format_output,
)

SYMBOL_CORE_MAIN = "scip-python python app 0.1 src/core/main()."
SYMBOL_CORE_HELPER = "scip-python python app 0.1 src/core/helper()."
SYMBOL_API_HANDLER = "scip-python python app 0.1 src/api/handler()."
SYMBOL_EXT = "scip-python python extpkg 0.1 vendor/ext/thing()."


def _make_block(symbol: str, start: int) -> CodeBlock:
    return CodeBlock(
        file_path="src/sample.py",
        start_line=start,
        end_line=start + 3,
        code=f"def line_{start}():\n    pass",
        symbol=symbol,
    )


def _make_result() -> TraversalResult:
    blocks = [
        _make_block(SYMBOL_CORE_MAIN, 1),
        _make_block(SYMBOL_CORE_HELPER, 10),
        _make_block(SYMBOL_API_HANDLER, 20),
        _make_block(SYMBOL_EXT, 30),
    ]
    return TraversalResult(
        layers={0: [blocks[0]], 1: blocks[1:]},
        collected_nodes=len(blocks),
        node_metadata={
            block.symbol: {
                "file": block.file_path,
                "lines": [block.start_line, block.end_line],
                "layer": 0 if i == 0 else 1,
                "is_test": False,
                "is_partial": False,
            }
            for i, block in enumerate(blocks)
        },
        edges=[
            GraphEdge(from_symbol=SYMBOL_CORE_MAIN, to_symbol=SYMBOL_CORE_HELPER, edge_type="reference"),
            GraphEdge(from_symbol=SYMBOL_CORE_HELPER, to_symbol=SYMBOL_API_HANDLER, edge_type="reference"),
            GraphEdge(from_symbol=SYMBOL_API_HANDLER, to_symbol=SYMBOL_EXT, edge_type="reference"),
        ],
    )


def _parse_frontmatter(markdown: str) -> dict:
    _, rest = markdown.split("---\n", 1)
    frontmatter, _ = rest.split("---\n", 1)
    return yaml.safe_load(frontmatter)


def _parse_cli(extra_args: list[str]):
    return parse_args(
        [
            "--scip-file",
            "index.scip",
            "--project-root",
            ".",
            "--entry-file",
            "src/sample.py",
            "--entry-line",
            "1",
            *extra_args,
        ]
    )


def test_matches_output_modules_exact_and_wildcard() -> None:
    assert _matches_output_modules(SYMBOL_CORE_MAIN, ["app"])
    assert _matches_output_modules(SYMBOL_CORE_MAIN, ["ap*"])


def test_matches_output_modules_no_match_and_empty_input() -> None:
    assert not _matches_output_modules(SYMBOL_CORE_MAIN, ["other"])
    assert not _matches_output_modules("not-a-valid-scip-symbol", ["app"])
    assert not _matches_output_modules(SYMBOL_CORE_MAIN, [])


def test_matches_output_symbol_prefix_basic_cases() -> None:
    assert _matches_output_symbol_prefix(SYMBOL_CORE_MAIN, ["src/core/"])
    assert _matches_output_symbol_prefix(SYMBOL_CORE_MAIN, ["src/core/main()."])
    assert not _matches_output_symbol_prefix(SYMBOL_CORE_MAIN, ["src/Core/"])
    assert _matches_output_symbol_prefix(SYMBOL_API_HANDLER, ["src/none/", "src/api/"])
    assert not _matches_output_symbol_prefix(SYMBOL_API_HANDLER, ["src/none/"])


def test_matches_output_symbol_prefix_empty_and_local() -> None:
    assert _matches_output_symbol_prefix(SYMBOL_CORE_MAIN, [])
    assert _matches_output_symbol_prefix("local 1", ["local "])


def test_parse_args_output_symbol_prefix_ignores_empty_tokens() -> None:
    args = _parse_cli(["--output-symbol-prefix", "src/core/,,src/api/, ,"])
    assert args.output_symbol_prefix == ["src/core/", "src/api/"]


def test_parse_args_output_symbol_prefix_strips_and_dedups() -> None:
    args = _parse_cli(["--output-symbol-prefix", " src/core/ , src/core/ , src/api/ "])
    assert args.output_symbol_prefix == ["src/core/", "src/api/"]


def test_parse_args_output_symbol_prefix_empty_or_whitespace() -> None:
    assert _parse_cli(["--output-symbol-prefix", ""]).output_symbol_prefix == []
    assert _parse_cli(["--output-symbol-prefix", "   "]).output_symbol_prefix == []


def test_format_output_no_filter_hides_rendered_nodes() -> None:
    output = format_output(_make_result(), 10)
    frontmatter = _parse_frontmatter(output)
    assert "rendered_nodes" not in frontmatter


def test_format_output_module_filter_sets_rendered_nodes() -> None:
    output = format_output(_make_result(), 10, output_modules=["app"])
    frontmatter = _parse_frontmatter(output)
    assert frontmatter["rendered_nodes"] == 3


def test_format_output_symbol_prefix_filter_sets_rendered_nodes() -> None:
    output = format_output(_make_result(), 10, output_symbol_prefix=["src/core/"])
    frontmatter = _parse_frontmatter(output)
    assert frontmatter["rendered_nodes"] == 2


def test_format_output_both_filters_use_and_relation() -> None:
    output = format_output(
        _make_result(),
        10,
        output_modules=["app"],
        output_symbol_prefix=["src/api/"],
    )
    frontmatter = _parse_frontmatter(output)
    assert frontmatter["rendered_nodes"] == 1
    assert "### src/api/handler()." in output
    assert "### src/core/main()." not in output


def test_format_output_no_match_renders_zero_nodes() -> None:
    output = format_output(_make_result(), 10, output_symbol_prefix=["does/not/exist/"])
    frontmatter = _parse_frontmatter(output)
    assert frontmatter["rendered_nodes"] == 0
    assert "## Layer 0" not in output
    assert "## Layer 1" not in output


def test_format_output_summary_keeps_full_bfs_context() -> None:
    output = format_output(
        _make_result(),
        10,
        output_modules=["app"],
        output_symbol_prefix=["src/core/"],
    )
    assert "- `app`: 3" in output
    assert "- `extpkg`: 1" in output


def test_rendered_nodes_matrix() -> None:
    scenarios = [
        (None, None, False, None),
        (["app"], None, True, 3),
        (None, ["src/core/"], True, 2),
        (["app"], ["src/core/"], True, 2),
    ]
    for modules, prefixes, has_field, expected_count in scenarios:
        output = format_output(
            _make_result(),
            10,
            output_modules=modules,
            output_symbol_prefix=prefixes,
        )
        frontmatter = _parse_frontmatter(output)
        if has_field:
            assert frontmatter["rendered_nodes"] == expected_count
        else:
            assert "rendered_nodes" not in frontmatter


def test_format_output_bfs_unaffected_by_output_filters() -> None:
    """Verify collected_nodes in frontmatter reflects full BFS, not filtered subset."""
    output = format_output(
        _make_result(),
        10,
        output_modules=["app"],
        output_symbol_prefix=["src/core/"],
    )
    frontmatter = _parse_frontmatter(output)
    assert frontmatter["collected_nodes"] == 4
    assert frontmatter["rendered_nodes"] == 2


def test_format_graph_json_unaffected_by_output_filters(tmp_path) -> None:
    scip_file = tmp_path / "sample.scip"
    scip_file.write_bytes(b"scip")
    graph = json.loads(
        format_graph_json(
            _make_result(),
            entry_file="src/sample.py",
            entry_line=1,
            entry_symbol=SYMBOL_CORE_MAIN,
            scip_file=str(scip_file),
        )
    )
    assert len(graph["nodes"]) == 4
