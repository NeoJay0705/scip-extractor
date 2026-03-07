from __future__ import annotations

import fnmatch
import re
from typing import List, Optional

from scip_deep_context.path_resolver import is_within_project


def parse_package(symbol: str) -> Optional[str]:
    """Extract the package segment from a SCIP symbol.

    For 5+ part symbols: 3rd field. For 2-part symbols: 1st field.
    """
    parts = symbol.split(" ")
    if len(parts) >= 3:
        pkg = parts[2]
        return pkg if pkg else None
    if len(parts) == 2:
        return parts[0]
    return None


def match_module_patterns(pkg: str, patterns: List[str]) -> bool:
    """Check if a package name matches any given module patterns."""
    for mod in patterns:
        if not mod:
            continue
        if mod.endswith("*"):
            prefix = mod[:-1]
            if pkg.startswith(prefix):
                return True
        elif pkg == mod:
            return True
    return False


class SymbolFilter:
    def __init__(
        self,
        project_modules: List[str],
        project_root: str,
        exclude_patterns: List[str],
    ):
        self._modules = [m.strip() for m in project_modules]
        self._project_root = project_root
        self._exclude_patterns = exclude_patterns

    def is_internal(self, symbol: str, definition_uri: Optional[str] = None) -> bool:
        """Three-layer filter: whitelist → URI fallback → blacklist."""
        passed = False
        pkg = parse_package(symbol)

        if self._modules and pkg:
            # Layer 1: whitelist check
            passed = match_module_patterns(pkg, self._modules)
        else:
            # Layer 2: URI fallback
            if definition_uri is not None:
                passed = is_within_project(definition_uri, self._project_root)
            else:
                passed = False

        if not passed:
            return False

        # Layer 3: blacklist / exclude patterns
        for pattern in self._exclude_patterns:
            if fnmatch.fnmatch(symbol, pattern):
                return False

        return True


_PARAM_DESCRIPTOR_RE = re.compile(r'\.\([^)]+\)$')


def _is_parameter_symbol(symbol: str) -> bool:
    """Check if symbol is a parameter (descriptor ends with .(name))."""
    return bool(_PARAM_DESCRIPTOR_RE.search(symbol))


def _has_empty_param_descriptor(symbol: str) -> bool:
    """Detect invalid empty parameter descriptor ``.()```` in symbol."""
    return ".()" in symbol


def is_local_symbol(symbol: str) -> bool:
    """Check if symbol is a SCIP local symbol (starts with ``local ``)."""
    return symbol.startswith("local ")


def is_function_like(symbol: str) -> bool:
    """判定 SCIP symbol 是否為 function-like。

    排除 parameter symbols（descriptor 格式 ``method().(param)``）
    及含無效空參數段 ``.()```` 的異常 descriptor。
    """
    if "()" not in symbol:
        return False
    if _has_empty_param_descriptor(symbol):
        return False
    return not _is_parameter_symbol(symbol)


def is_field_like(symbol: str) -> bool:
    """判定 SCIP symbol 是否為 field/property（term descriptor，不含 ``()``）。

    SCIP descriptor suffix 規則：``.`` = term（field/property/variable），
    ``#`` = type，``/`` = namespace，``()`` = method。
    本函數僅放行 term descriptor，排除 type/namespace/local。
    """
    if "()" in symbol:
        return False
    return symbol.rstrip().endswith(".")
