"""CLI entry point for SCIP Deep Context Extractor."""
from __future__ import annotations

import argparse
import sys

from scip_deep_context.models import CLIArgs
from scip_deep_context.path_resolver import PathResolverError, resolve_entry_file
from scip_deep_context.scip_loader import SCIPLoadError, build_symbol_table, load_scip
from scip_deep_context.entry_locator import NoReferenceFoundError, locate_entry_symbol
from scip_deep_context.symbol_filter import SymbolFilter
from scip_deep_context.bfs_traverser import traverse
from scip_deep_context.output_formatter import format_output, format_graph_json

_DEFAULT_EXCLUDES = ["local *"]


def _parse_csv(value: str, *, dedup: bool = False) -> list[str]:
    """Parse a comma-separated string into a list of stripped, non-empty tokens."""
    if not value or not value.strip():
        return []
    tokens = [token.strip() for token in value.split(",") if token.strip()]
    if not dedup:
        return tokens
    unique: list[str] = []
    seen: set[str] = set()
    for token in tokens:
        if token not in seen:
            seen.add(token)
            unique.append(token)
    return unique


def parse_args(argv=None) -> CLIArgs:
    parser = argparse.ArgumentParser(description="SCIP Deep Context Extractor")
    parser.add_argument("--scip-file", required=True)
    parser.add_argument("--project-root", required=True)
    parser.add_argument("--entry-file", default=None)
    parser.add_argument("--entry-line", type=int, default=None)
    parser.add_argument("--test-file-pattern", default=None,
        help="Glob pattern to match test file names for batch extract")
    parser.add_argument("--test-method-pattern", default=None,
        help="Glob pattern to match test method names for batch extract")
    parser.add_argument("--project-modules", default="")
    parser.add_argument("--output-modules", default="",
        help="Comma-separated modules for Markdown output filtering (BFS unchanged)")
    parser.add_argument("--output-symbol-prefix", default="",
        help="Comma-separated descriptor prefixes for Markdown output filtering. "
             "Uses string prefix matching on the SCIP descriptor part. "
             "AND relation with --output-modules when both specified. "
             "Use --raw-symbols to inspect actual descriptor formats.")
    parser.add_argument("--max-nodes", type=int, default=10)
    parser.add_argument("--timeout", type=float, default=3.0)
    parser.add_argument("--exclude-patterns", default="")
    parser.add_argument("--no-dedup", action="store_true", default=False,
        help="Disable containment dedup (output all collected blocks)")
    parser.add_argument("--raw-symbols", action="store_true", default=False,
        help="Output full SCIP symbol in section headers (default: descriptor only)")
    parser.add_argument("--no-default-excludes", action="store_true", default=False,
        help="Disable default exclude patterns (e.g. 'local *')")
    parser.add_argument("--graph-output", default=None,
        help="Write call graph to JSON file at the given path")
    parser.add_argument("--include-fields", action="store_true", default=False,
        help="Include field/property symbols in BFS traversal (default: excluded)")
    parser.add_argument("--version", action="version", version="%(prog)s 0.7.0")
    args = parser.parse_args(argv)

    # 互斥驗證：single entry vs batch test
    has_single = args.entry_file is not None or args.entry_line is not None
    has_batch = args.test_file_pattern is not None or args.test_method_pattern is not None
    if has_single and has_batch:
        parser.error("--entry-file/--entry-line and --test-file-pattern/--test-method-pattern are mutually exclusive")
    if not has_single and not has_batch:
        parser.error("Must specify either --entry-file + --entry-line or --test-file-pattern/--test-method-pattern")
    if has_single and (args.entry_file is None or args.entry_line is None):
        parser.error("--entry-file and --entry-line must be specified together")

    modules = _parse_csv(args.project_modules)
    output_modules = _parse_csv(args.output_modules)
    output_symbol_prefix = _parse_csv(args.output_symbol_prefix, dedup=True)
    user_patterns = _parse_csv(args.exclude_patterns)
    if args.no_default_excludes:
        patterns = user_patterns
    else:
        patterns = _DEFAULT_EXCLUDES + user_patterns

    return CLIArgs(
        scip_file=args.scip_file,
        project_root=args.project_root,
        entry_file=args.entry_file,
        entry_line=args.entry_line,
        project_modules=modules,
        output_modules=output_modules,
        max_nodes=args.max_nodes,
        timeout=args.timeout,
        exclude_patterns=patterns,
        dedup=not args.no_dedup,
        raw_symbols=args.raw_symbols,
        graph_output=args.graph_output,
        test_file_pattern=args.test_file_pattern,
        test_method_pattern=args.test_method_pattern,
        include_fields=args.include_fields,
        output_symbol_prefix=output_symbol_prefix,
    )


def main(argv=None) -> int:
    args = parse_args(argv)

    # Batch test extract mode
    if args.test_file_pattern is not None or args.test_method_pattern is not None:
        return _batch_extract(args)

    # Single entry point mode
    try:
        entry_file = resolve_entry_file(args.project_root, args.entry_file)
    except PathResolverError as e:
        print(str(e), file=sys.stderr)
        return 3

    try:
        index = load_scip(args.scip_file)
        symbol_table = build_symbol_table(index)
        entry_symbol = locate_entry_symbol(symbol_table, entry_file, args.entry_line)
    except (SCIPLoadError, NoReferenceFoundError) as e:
        print(str(e), file=sys.stderr)
        return 2

    sf = SymbolFilter(args.project_modules, args.project_root, args.exclude_patterns)
    result = traverse(entry_symbol, symbol_table, sf, args.project_root, args.max_nodes, args.timeout, include_fields=args.include_fields)

    output = format_output(
        result,
        args.max_nodes,
        dedup=args.dedup,
        raw_symbols=args.raw_symbols,
        output_modules=args.output_modules,
        output_symbol_prefix=args.output_symbol_prefix,
    )
    sys.stdout.write(output)

    # Graph JSON output (opt-in via --graph-output)
    if args.graph_output:
        graph_json = format_graph_json(
            result,
            entry_file=entry_file,
            entry_line=args.entry_line,
            entry_symbol=entry_symbol,
            scip_file=args.scip_file,
            context_file=None,
            raw_symbols=args.raw_symbols,
            dedup=args.dedup,
        )
        with open(args.graph_output, "w", encoding="utf-8") as f:
            f.write(graph_json)

    if result.broken_links:
        return 1
    return 0


def _batch_extract(args: CLIArgs) -> int:
    """Batch extract mode: find test symbols and extract all of them."""
    from scip_deep_context.test_extractor import extract_test_symbols
    from scip_deep_context.graph_merger import merge_graphs

    try:
        index = load_scip(args.scip_file)
        symbol_table = build_symbol_table(index)
    except SCIPLoadError as e:
        print(str(e), file=sys.stderr)
        return 2

    test_symbols = extract_test_symbols(
        symbol_table,
        file_pattern=args.test_file_pattern,
        method_pattern=args.test_method_pattern,
    )

    if not test_symbols:
        print("No test symbols match the given pattern(s)", file=sys.stderr)
        return 2

    sf = SymbolFilter(args.project_modules, args.project_root, args.exclude_patterns)
    all_graphs = []
    all_outputs = []
    all_broken_links = []

    for sym_key, file_uri, line in test_symbols:
        result = traverse(sym_key, symbol_table, sf, args.project_root, args.max_nodes, args.timeout, include_fields=args.include_fields)
        all_broken_links.extend(result.broken_links)
        output = format_output(
            result,
            args.max_nodes,
            dedup=args.dedup,
            raw_symbols=args.raw_symbols,
            output_modules=args.output_modules,
            output_symbol_prefix=args.output_symbol_prefix,
        )
        all_outputs.append(output)

        if args.graph_output:
            graph_json_str = format_graph_json(
                result,
                entry_file=file_uri,
                entry_line=line + 1,  # 0-based → 1-based
                entry_symbol=sym_key,
                scip_file=args.scip_file,
                context_file=None,
                raw_symbols=args.raw_symbols,
                dedup=args.dedup,
            )
            import json
            all_graphs.append(json.loads(graph_json_str))

    # Output merged Markdown
    sys.stdout.write("\n".join(all_outputs))

    # Output merged graph
    if args.graph_output and all_graphs:
        if len(all_graphs) == 1:
            merged = all_graphs[0]
        else:
            merged = merge_graphs(all_graphs)
        import json
        with open(args.graph_output, "w", encoding="utf-8") as f:
            json.dump(merged, f, indent=2, ensure_ascii=False)

    return 1 if all_broken_links else 0


def merge_main(argv=None) -> int:
    """CLI entry point for scip-graph-merge."""
    parser = argparse.ArgumentParser(description="Merge multiple SCIP graph JSON files")
    parser.add_argument("inputs", nargs="+", help="Input .graph.json files")
    parser.add_argument("-o", "--output", required=True, help="Output merged graph JSON path")
    args = parser.parse_args(argv)

    from scip_deep_context.graph_merger import (
        IndexHashMismatchError,
        load_graph,
        merge_graphs,
        save_graph,
    )

    try:
        graphs = [load_graph(p) for p in args.inputs]
        merged = merge_graphs(graphs)
        save_graph(merged, args.output)
    except IndexHashMismatchError as e:
        print(f"Fatal: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 2

    return 0


def query_main(argv=None) -> int:
    """CLI entry point for scip-graph-query."""
    import json

    parser = argparse.ArgumentParser(description="Query a unified SCIP graph")
    parser.add_argument("--graph", required=True, metavar="PATH",
        help="Unified graph JSON path")
    parser.add_argument("--max-depth", type=int, default=10, metavar="N",
        help="Maximum traversal depth (default: 10)")
    parser.add_argument("--with-source", action="store_true", default=False,
        help="Attach source code snippets (switches output to Markdown)")
    parser.add_argument("--project-root", default=None, metavar="PATH",
        help="Project root for source file lookup (required with --with-source)")

    mode_group = parser.add_mutually_exclusive_group(required=True)
    mode_group.add_argument("--list-nodes", action="store_true",
        help="List all node keys in the graph")
    mode_group.add_argument("--forward-from", metavar="NODE_KEY",
        help="Q1: forward transitive query")
    mode_group.add_argument("--reverse-from", metavar="NODE_KEY",
        help="Q2: reverse transitive query")
    mode_group.add_argument("--test-impact", metavar="NODE_KEY",
        help="Q3: reverse query filtered to test nodes")
    mode_group.add_argument("--coverage", metavar="NODE_KEY",
        help="Q4: forward query filtered to impl nodes")
    args = parser.parse_args(argv)

    if args.with_source and args.list_nodes:
        parser.error("--with-source and --list-nodes are mutually exclusive")
    if args.with_source and not args.project_root:
        parser.error("--project-root is required when --with-source is enabled")

    from scip_deep_context.graph_merger import load_graph
    from scip_deep_context.graph_query import GraphQuery

    try:
        graph = load_graph(args.graph)
    except Exception as e:
        print(f"Error loading graph: {e}", file=sys.stderr)
        return 2

    gq = GraphQuery(graph)

    if args.list_nodes:
        for key in gq.list_nodes():
            print(key)
        return 0

    max_depth = args.max_depth

    # Resolve node key (supports glob patterns)
    raw_key = args.forward_from or args.reverse_from or args.test_impact or args.coverage
    resolved_key, matches = gq.resolve_node_key(raw_key)
    if resolved_key is None:
        print(f"No node matches pattern: {raw_key}", file=sys.stderr)
        return 2
    if len(matches) > 1:
        print(f"Pattern '{raw_key}' matched {len(matches)} nodes, using '{resolved_key}':", file=sys.stderr)
        for m in matches:
            print(f"  {m}", file=sys.stderr)

    if args.forward_from:
        query_type = "forward_from"
        result = gq.forward_from(resolved_key, max_depth)
    elif args.reverse_from:
        query_type = "reverse_from"
        result = gq.reverse_from(resolved_key, max_depth)
    elif args.test_impact:
        query_type = "test_impact"
        result = gq.test_impact(resolved_key, max_depth)
    else:
        query_type = "coverage"
        result = gq.coverage(resolved_key, max_depth)

    if args.with_source:
        from scip_deep_context.output_formatter import format_query_markdown

        md = format_query_markdown(
            result,
            query_type=query_type,
            entry_node=resolved_key,
            project_root=args.project_root,
        )
        sys.stdout.write(md)
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    if result.get("is_truncated"):
        print(f"Warning: result truncated at max_depth={max_depth}", file=sys.stderr)
    for warning in result.get("warnings", []):
        print(f"Warning: {warning}", file=sys.stderr)

    return 0
