from __future__ import annotations

import ast
import os
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

mcp: FastMCP = FastMCP("code-intelligence")


def get_file_structure(file_path: str) -> dict[str, Any]:
    result: dict[str, Any] = {
        "file": file_path,
        "imports": [],
        "classes": [],
        "functions": [],
        "error": None,
    }
    try:
        source = Path(file_path).read_text(encoding="utf-8")
    except FileNotFoundError:
        result["error"] = f"File not found: {file_path}"
        return result
    except OSError as exc:
        result["error"] = str(exc)
        return result

    try:
        tree = ast.parse(source, filename=file_path)
    except SyntaxError as exc:
        result["error"] = f"Syntax error: {exc.msg} (line {exc.lineno})"
        return result

    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                result["imports"].append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            for alias in node.names:
                result["imports"].append(f"{module}.{alias.name}" if module else alias.name)
        elif isinstance(node, ast.ClassDef):
            result["classes"].append(node.name)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            result["functions"].append(node.name)

    return result


def find_references(symbol_name: str, project_root: str) -> dict[str, Any]:
    result: dict[str, Any] = {
        "symbol": symbol_name,
        "references": [],
        "count": 0,
        "error": None,
    }
    root = Path(project_root)
    if not root.is_dir():
        result["error"] = f"Project root not found: {project_root}"
        return result

    for dirpath, _dirnames, filenames in os.walk(root):
        for fname in filenames:
            if not fname.endswith(".py"):
                continue
            fpath = Path(dirpath) / fname
            try:
                lines = fpath.read_text(encoding="utf-8").splitlines()
            except OSError:
                continue
            for lineno, line in enumerate(lines, start=1):
                if symbol_name in line:
                    result["references"].append(
                        {
                            "file": str(fpath),
                            "line": lineno,
                            "content": line,
                        }
                    )

    result["count"] = len(result["references"])
    return result


def get_impact_analysis(file_path: str, project_root: str) -> dict[str, Any]:
    result: dict[str, Any] = {
        "changed_file": file_path,
        "defines": [],
        "impacted_files": [],
        "count": 0,
        "error": None,
    }
    structure = get_file_structure(file_path)
    if structure["error"] is not None:
        result["error"] = structure["error"]
        return result

    defines: list[str] = structure["classes"] + structure["functions"]
    result["defines"] = defines

    file_refs: dict[str, set[str]] = {}
    for symbol in defines:
        refs = find_references(symbol, project_root)
        for ref in refs["references"]:
            ref_file = ref["file"]
            normalized = str(Path(ref_file))
            if normalized == str(Path(file_path)):
                continue
            if normalized not in file_refs:
                file_refs[normalized] = set()
            file_refs[normalized].add(symbol)

    result["impacted_files"] = [
        {"file": f, "references": sorted(syms)} for f, syms in sorted(file_refs.items())
    ]
    result["count"] = len(result["impacted_files"])
    return result


@mcp.tool()
def tool_get_file_structure(file_path: str) -> dict[str, Any]:
    return get_file_structure(file_path)


@mcp.tool()
def tool_find_references(symbol_name: str, project_root: str) -> dict[str, Any]:
    return find_references(symbol_name, project_root)


@mcp.tool()
def tool_get_impact_analysis(file_path: str, project_root: str) -> dict[str, Any]:
    return get_impact_analysis(file_path, project_root)


if __name__ == "__main__":
    mcp.run()
