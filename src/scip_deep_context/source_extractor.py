"""Source extractor — extract code blocks with three-level fallback."""
from __future__ import annotations

import os
import tokenize
import io
from typing import List, Optional, Protocol

from scip_deep_context.models import CodeBlock, SymbolInfo


class FileReader(Protocol):
    def read_lines(self, path: str) -> List[str]: ...


class RealFileReader:
    def read_lines(self, path: str) -> List[str]:
        with open(path, encoding="utf-8") as f:
            return f.readlines()


def extract_source(
    symbol: str,
    symbol_info: SymbolInfo,
    project_root: str,
    file_reader: Optional[FileReader] = None,
) -> CodeBlock:
    """Extract source code for *symbol* using three-level fallback.

    Fallback order:
    1. Enclosing range from definition occurrence
    2. Indent detection from definition line
    3. ±5 lines around definition
    4. file_missing placeholder
    """
    if file_reader is None:
        file_reader = RealFileReader()

    if not symbol_info.definitions:
        return CodeBlock(
            file_path="",
            start_line=0,
            end_line=0,
            code="",
            symbol=symbol,
            extraction_method="file_missing",
            is_file_missing=True,
        )

    def_occ = symbol_info.definitions[0]
    file_path = os.path.join(project_root, def_occ.file_uri)

    try:
        lines = file_reader.read_lines(file_path)
    except (FileNotFoundError, OSError):
        return CodeBlock(
            file_path=def_occ.file_uri,
            start_line=def_occ.line + 1,
            end_line=def_occ.line + 1,
            code="",
            symbol=symbol,
            extraction_method="file_missing",
            is_file_missing=True,
        )

    # Fallback 1: enclosing_range
    if def_occ.enclosing_range is not None:
        sr, sc, er, ec = def_occ.enclosing_range
        start = max(sr, 0)
        end = min(er + 1, len(lines))
        code = "".join(lines[start:end])
        return CodeBlock(
            file_path=def_occ.file_uri,
            start_line=start + 1,
            end_line=end,
            code=code,
            symbol=symbol,
            extraction_method="enclosing_range",
        )

    # Fallback 2: indent detection
    def_line_idx = def_occ.line
    if 0 <= def_line_idx < len(lines):
        language = _lang_from_ext(def_occ.file_uri)
        block_lines = _detect_indent_block(lines, def_line_idx, language=language)
        if block_lines is not None:
            start_idx, end_idx = block_lines
            code = "".join(lines[start_idx:end_idx])
            return CodeBlock(
                file_path=def_occ.file_uri,
                start_line=start_idx + 1,
                end_line=end_idx,
                code=code,
                symbol=symbol,
                extraction_method="indent_detection",
                is_partial=True,
            )

    # Fallback 3: ±5 lines
    start = max(def_line_idx - 5, 0)
    end = min(def_line_idx + 6, len(lines))
    code = "".join(lines[start:end])
    return CodeBlock(
        file_path=def_occ.file_uri,
        start_line=start + 1,
        end_line=end,
        code=code,
        symbol=symbol,
        extraction_method="fallback_5lines",
        is_partial=True,
    )


def read_source_by_range(
    project_root: str,
    file_path: str,
    start_line: int,
    end_line: int,
) -> str:
    """Read source code by line range (1-based, inclusive)."""
    abs_path = os.path.join(project_root, file_path)
    safe_start = max(1, start_line)
    safe_end = max(safe_start, end_line)
    try:
        with open(abs_path, encoding="utf-8") as f:
            lines = f.readlines()
    except (FileNotFoundError, OSError):
        return f"# Source not available: {file_path}"

    return "".join(lines[safe_start - 1:safe_end]).rstrip("\n")


def _lang_from_ext(file_path: str) -> str:
    """從檔案副檔名推斷語言。"""
    ext = os.path.splitext(file_path)[1].lower()
    return {
        ".go": "go",
        ".ts": "typescript", ".tsx": "typescript",
        ".js": "javascript", ".jsx": "javascript",
    }.get(ext, "python")


def _strip_comment(line: str, language: str = "python") -> str:
    """Remove trailing comment, dispatching by language."""
    if language == "python":
        return _strip_comment_python(line)
    return _strip_comment_c_style(line)


def _strip_comment_python(line: str) -> str:
    """Remove trailing comment from a Python source line, respecting strings.

    Uses ``tokenize`` so that ``#`` inside string literals is preserved.
    Falls back to the raw line (stripped) if tokenization fails.
    """
    try:
        tokens = list(tokenize.generate_tokens(io.StringIO(line).readline))
        # Find the first COMMENT token and return everything before it
        for tok in tokens:
            if tok.type == tokenize.COMMENT:
                return line[: tok.start[1]].rstrip()
        return line.rstrip()
    except tokenize.TokenError:
        # Incomplete expression (e.g. multi-line string) — return as-is
        return line.rstrip()


def _strip_comment_c_style(line: str) -> str:
    """Remove C-style ``//`` line comment, respecting string literals."""
    in_string = None
    i = 0
    while i < len(line):
        ch = line[i]
        if in_string:
            if ch == '\\':
                i += 2
                continue
            if ch == in_string:
                in_string = None
        else:
            if ch in ('"', "'", '`'):
                in_string = ch
            elif ch == '/' and i + 1 < len(line) and line[i + 1] == '/':
                return line[:i].rstrip()
        i += 1
    return line.rstrip()


def _detect_indent_block(
    lines: List[str], start_idx: int, language: str = "python"
) -> Optional[tuple]:
    """Detect a code block starting at *start_idx*, dispatching by language."""
    if language == "python":
        return _detect_python_block(lines, start_idx)
    return _detect_brace_block(lines, start_idx)


def _detect_python_block(lines: List[str], start_idx: int) -> Optional[tuple]:
    """Detect an indentation-based block starting at *start_idx*.

    Returns (start_idx, end_idx_exclusive) or None if detection fails.
    """
    if start_idx >= len(lines):
        return None

    first_line = lines[start_idx]
    stripped = first_line.rstrip("\n\r")
    if not stripped:
        return None

    base_indent = len(stripped) - len(stripped.lstrip())

    # Check if the line ends with ':', indicating a block definition
    # Strip inline comment before checking (REQ-05)
    # Use tokenize to avoid mis-splitting '#' inside strings (e.g. def f(s="#"):)
    code_part = _strip_comment_python(stripped)
    if not code_part.endswith(":"):
        return None

    end_idx = start_idx + 1
    while end_idx < len(lines):
        line = lines[end_idx]
        stripped_line = line.rstrip("\n\r")
        if not stripped_line:
            # blank line — continue
            end_idx += 1
            continue
        current_indent = len(stripped_line) - len(stripped_line.lstrip())
        if current_indent <= base_indent:
            break
        end_idx += 1

    if end_idx == start_idx + 1:
        return None

    return (start_idx, end_idx)


def _detect_brace_block(lines: List[str], start_idx: int) -> Optional[tuple]:
    """Brace-based block detection (Go / TypeScript / JavaScript)."""
    if start_idx >= len(lines):
        return None
    first_line = lines[start_idx].rstrip("\n\r")
    if not first_line.strip():
        return None
    # Scan for '{' on start_idx or up to 2 lines ahead (Allman style)
    brace_start = None
    for offset in range(3):
        idx = start_idx + offset
        if idx >= len(lines):
            break
        code_part = _strip_comment_c_style(lines[idx].rstrip("\n\r"))
        if '{' in code_part:
            brace_start = idx
            break
        if offset > 0 and code_part.strip():
            break  # non-empty, non-brace content — not a block start
    if brace_start is None:
        return None
    # Count brace depth
    depth = 0
    end_idx = brace_start
    while end_idx < len(lines):
        line = lines[end_idx].rstrip("\n\r")
        stripped = _strip_comment_c_style(line)
        for ch in stripped:
            if ch == '{':
                depth += 1
            elif ch == '}':
                depth -= 1
                if depth == 0:
                    return (start_idx, end_idx + 1)
        end_idx += 1
    return None
