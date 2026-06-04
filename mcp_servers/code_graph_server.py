from __future__ import annotations

import os
import sys
from typing import Any

from mcp.server.fastmcp import FastMCP

mcp: FastMCP = FastMCP("code-graph")

NEO4J_DATABASE = os.environ.get("NEO4J_DATABASE", "nanaka-code-graph")

print(f"[DEBUG] NEO4J_URI={os.environ.get('NEO4J_URI', 'NOT SET')}", file=sys.stderr)
print(f"[DEBUG] NEO4J_USER={os.environ.get('NEO4J_USER', 'NOT SET')}", file=sys.stderr)
print(f"[DEBUG] NEO4J_PASSWORD={'SET' if os.environ.get('NEO4J_PASSWORD') else 'NOT SET'}", file=sys.stderr)
print(f"[DEBUG] NEO4J_DATABASE={NEO4J_DATABASE}", file=sys.stderr)

_driver: Any = None


def _reset_driver() -> None:
    global _driver
    if _driver is not None:
        try:
            _driver.close()
        except Exception:
            pass
    _driver = None


def _get_driver() -> Any:
    global _driver
    if _driver is not None:
        return _driver
    uri = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
    user = os.environ.get("NEO4J_USER", "neo4j")
    password = os.environ.get("NEO4J_PASSWORD", "")
    try:
        from neo4j import GraphDatabase

        driver = GraphDatabase.driver(uri, auth=(user, password))
        driver.verify_connectivity()
        _driver = driver
    except Exception as e:
        print(f"[DEBUG] Neo4j connection failed: {e}", file=sys.stderr)
        _driver = None
    return _driver


def get_impact_analysis_graph(file_path: str) -> dict[str, Any]:
    driver = _get_driver()
    if driver is None:
        return {
            "changed_file": file_path,
            "defines": [],
            "impacted_files": [],
            "count": 0,
            "source": "error",
            "error": "Neo4j未起動または接続失敗",
            "fallback": "tool_get_impact_analysis（ast版）を使用してください",
        }

    with driver.session(database=NEO4J_DATABASE) as session:
        define_result = session.run(
            """
            MATCH (f:File {path: $file_path})-[:DEFINES]->(sym)
            WHERE sym:Function OR sym:Class
            RETURN sym.name AS sym_name
            """,
            file_path=file_path,
        )
        defines = [record["sym_name"] for record in define_result]

        impact_result = session.run(
            """
            MATCH (f:File {path: $file_path})-[:DEFINES]->(sym)
            WHERE sym:Function OR sym:Class
            WITH sym
            MATCH (other:File)-[:DEFINES]->(caller:Function)-[:CALLS]->(sym)
            WHERE other.path <> $file_path
            RETURN other.path AS file, collect(DISTINCT sym.name) AS via_symbols
            """,
            file_path=file_path,
        )
        impacted_files = [
            {"file": record["file"], "via_symbols": record["via_symbols"]}
            for record in impact_result
        ]

    return {
        "changed_file": file_path,
        "defines": defines,
        "impacted_files": impacted_files,
        "count": len(impacted_files),
        "source": "neo4j",
    }


def get_call_graph(function_name: str, depth: int = 2) -> dict[str, Any]:
    if depth < 1:
        return {
            "function": function_name,
            "depth": depth,
            "calls": [],
            "count": 0,
            "source": "error",
            "error": "depth must be a positive integer",
        }

    driver = _get_driver()
    if driver is None:
        return {
            "function": function_name,
            "depth": depth,
            "calls": [],
            "count": 0,
            "source": "error",
            "error": "Neo4j未起動または接続失敗",
            "fallback": "tool_find_references（ast版）を使用してください",
        }

    with driver.session(database=NEO4J_DATABASE) as session:
        result = session.run(
            """
            MATCH path = (fn:Function {name: $function_name})-[:CALLS*1..$depth]->(callee)
            WITH relationships(path) AS rels, nodes(path) AS nds
            UNWIND range(0, size(rels)-1) AS idx
            RETURN nds[idx].name AS from, nds[idx+1].name AS to, idx+1 AS depth
            """,
            function_name=function_name,
            depth=depth,
        )
        seen: set[tuple[str, str, int]] = set()
        calls: list[dict[str, Any]] = []
        for record in result:
            key = (record["from"], record["to"], record["depth"])
            if key not in seen:
                seen.add(key)
                calls.append(
                    {
                        "from": record["from"],
                        "to": record["to"],
                        "depth": record["depth"],
                    }
                )

    return {
        "function": function_name,
        "depth": depth,
        "calls": calls,
        "count": len(calls),
        "source": "neo4j",
        "note": "Callee nodes may be merged across files if names are identical.",
    }


@mcp.tool()
def tool_get_impact_analysis_graph(file_path: str) -> dict[str, Any]:
    return get_impact_analysis_graph(file_path)


@mcp.tool()
def tool_get_call_graph(function_name: str, depth: int = 2) -> dict[str, Any]:
    return get_call_graph(function_name, depth)


if __name__ == "__main__":
    mcp.run()
