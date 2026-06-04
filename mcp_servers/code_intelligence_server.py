from __future__ import annotations

import ast
import os
import subprocess
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP
from neo4j import GraphDatabase

mcp: FastMCP = FastMCP("code-intelligence")

NEO4J_DATABASE = os.environ.get("NEO4J_DATABASE", "nanaka-code-graph")

_embed_model: Any = None
_neo4j_driver: Any = None
_neo4j_driver_initialized: bool = False


def _get_embed_model() -> Any:
    global _embed_model
    if _embed_model is None:
        from sentence_transformers import SentenceTransformer
        _embed_model = SentenceTransformer("all-MiniLM-L6-v2")
    return _embed_model


def _get_neo4j_driver() -> Any:
    global _neo4j_driver, _neo4j_driver_initialized
    if _neo4j_driver_initialized:
        return _neo4j_driver
    _neo4j_driver_initialized = True
    uri = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
    user = os.environ.get("NEO4J_USER", "neo4j")
    password = os.environ.get("NEO4J_PASSWORD")
    if not password:
        return None
    try:
        driver = GraphDatabase.driver(uri, auth=(user, password))
        driver.verify_connectivity()
        _neo4j_driver = driver
    except Exception:
        _neo4j_driver = None
    return _neo4j_driver


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


def find_similar_code(query: str, top_k: int = 5) -> list[dict[str, Any]]:
    driver = _get_neo4j_driver()
    if driver is None:
        return [
            {
                "error": "Cannot connect to Neo4j or vector index not found. Run setup_vector_index.py first."
            }
        ]
    query_embedding = _get_embed_model().encode(query).tolist()
    with driver.session(database=NEO4J_DATABASE) as session:
        result = session.run(
            """
            CALL db.index.vector.queryNodes(
                'code_embeddings', $top_k, $embedding
            )
            YIELD node, score
            RETURN node.name AS function, node.file AS file, score
            ORDER BY score DESC
            """,
            top_k=top_k,
            embedding=query_embedding,
        )
        return [dict(r) for r in result]


@mcp.tool()
def tool_get_file_structure(file_path: str) -> dict[str, Any]:
    return get_file_structure(file_path)


@mcp.tool()
def tool_find_references(symbol_name: str, project_root: str) -> dict[str, Any]:
    return find_references(symbol_name, project_root)


@mcp.tool()
def tool_get_impact_analysis(file_path: str, project_root: str) -> dict[str, Any]:
    return get_impact_analysis(file_path, project_root)


@mcp.tool()
def tool_find_similar_code(query: str, top_k: int = 5) -> list[dict[str, Any]]:
    return find_similar_code(query, top_k=top_k)


def _graph_search(query: str, project_root: str) -> list[dict[str, Any]]:
    refs = find_references(query, project_root)
    return refs.get("references", [])


def _vector_search(query: str, top_k: int) -> list[dict[str, Any]]:
    result = find_similar_code(query, top_k=top_k)
    if result and "error" in result[0]:
        return []
    return result


def _reciprocal_rank_fusion(
    graph: list[dict[str, Any]],
    vector: list[dict[str, Any]],
    k: int = 60,
) -> list[dict[str, Any]]:
    scores: dict[str, float] = {}
    for rank, item in enumerate(graph):
        key = item.get("file", item.get("name", ""))
        scores[key] = scores.get(key, 0.0) + 1.0 / (k + rank + 1)
    for rank, item in enumerate(vector):
        key = item.get("file", "")
        scores[key] = scores.get(key, 0.0) + 1.0 / (k + rank + 1)
    return [
        {"file": f, "rrf_score": round(v, 6)}
        for f, v in sorted(scores.items(), key=lambda x: x[1], reverse=True)
    ][:5]


@mcp.tool()
def tool_hybrid_search(
    query: str,
    project_root: str = ".",
    top_k: int = 5,
) -> dict[str, Any]:
    graph_results = _graph_search(query, project_root)
    vector_results = _vector_search(query, top_k)
    hybrid_results = _reciprocal_rank_fusion(graph_results, vector_results)
    note = "hybrid_resultsはRRF統合済み・最も信頼性が高い"
    if not vector_results:
        note = "vector_search unavailable: Neo4j未起動またはインデックス未作成。graph_resultsのみでRRF。"
    return {
        "query": query,
        "graph_results": graph_results,
        "vector_results": vector_results,
        "hybrid_results": hybrid_results,
        "note": note,
    }


@mcp.tool()
def tool_get_file_history(
    file_path: str,
    max_commits: int = 10,
) -> list[dict[str, Any]]:
    result = subprocess.run(
        [
            "git", "log",
            f"--max-count={max_commits}",
            "--follow",
            "--format=%H|%ai|%s",
            "--",
            file_path,
        ],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        return [{"error": "Not a git repository or file not found."}]

    commits: list[dict[str, Any]] = []
    for line in result.stdout.splitlines():
        if "|" not in line:
            continue
        parts = line.split("|", 2)
        if len(parts) == 3:
            commits.append({
                "hash": parts[0][:8],
                "date": parts[1],
                "message": parts[2],
            })

    return commits


if __name__ == "__main__":
    mcp.run()
