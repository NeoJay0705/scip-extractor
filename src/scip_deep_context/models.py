from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntFlag
from typing import List, Optional, Tuple


class SymbolRole(IntFlag):
    DEFINITION = 0x1
    IMPORT = 0x2
    WRITE_ACCESS = 0x4
    READ_ACCESS = 0x8
    # Any non-definition occurrence is treated as a reference
    REFERENCE = 0x2 | 0x4 | 0x8
    TEST = 0x20


@dataclass(frozen=True)
class Occurrence:
    symbol: str
    line: int  # 0-based
    character: int  # 0-based
    roles: SymbolRole
    file_uri: str  # relative to project-root
    enclosing_range: Optional[Tuple[int, int, int, int]] = None


@dataclass(frozen=True)
class Relationship:
    symbol: str
    is_implementation: bool


@dataclass(frozen=True)
class SymbolInfo:
    symbol: str
    definitions: List[Occurrence]
    references: List[Occurrence]
    relationships: List[Relationship]


@dataclass(frozen=True)
class CodeBlock:
    file_path: str
    start_line: int  # 1-based
    end_line: int  # 1-based
    code: str
    symbol: str
    extraction_method: str = "enclosing_range"
    is_partial: bool = False
    is_file_missing: bool = False


@dataclass(frozen=True)
class BrokenLink:
    file_path: str
    line: int  # 1-based
    code_snippet: str
    reason: str  # "unresolved" | "no_definition" | "file_missing"


@dataclass(frozen=True)
class GraphEdge:
    from_symbol: str
    to_symbol: str
    edge_type: str  # "reference" | "implementation"


@dataclass
class TraversalResult:
    layers: dict = field(default_factory=dict)
    broken_links: List[BrokenLink] = field(default_factory=list)
    is_truncated: bool = False
    truncation_reasons: List[str] = field(default_factory=list)
    duration_sec: float = 0.0
    collected_nodes: int = 0
    edges: List[GraphEdge] = field(default_factory=list)
    node_metadata: dict = field(default_factory=dict)
    pending_symbols: List[str] = field(default_factory=list)


@dataclass(frozen=True)
class CLIArgs:
    scip_file: str
    project_root: str
    entry_file: Optional[str]
    entry_line: Optional[int]  # 1-based
    project_modules: List[str]
    max_nodes: int
    timeout: float
    exclude_patterns: List[str]
    dedup: bool = True           # --no-dedup 設為 False
    raw_symbols: bool = False    # --raw-symbols 設為 True
    graph_output: Optional[str] = None
    test_file_pattern: Optional[str] = None
    test_method_pattern: Optional[str] = None
    include_fields: bool = False     # --include-fields: include field symbols in BFS
    output_modules: List[str] = field(default_factory=list)
    output_symbol_prefix: List[str] = field(default_factory=list)


@dataclass(frozen=True)
class OutputMetadata:
    duration_sec: float
    collected_nodes: int
    max_nodes: int
    is_truncated: bool
    truncation_reasons: List[str]
    alerts_count: int
    rendered_nodes: Optional[int] = None


# --- Exceptions ---

class SCIPExtractError(Exception):
    pass


class InvalidInputError(SCIPExtractError):
    pass


class SCIPLoadError(InvalidInputError):
    pass


class NoReferenceFoundError(InvalidInputError):
    pass


class PathResolverError(SCIPExtractError):
    pass
