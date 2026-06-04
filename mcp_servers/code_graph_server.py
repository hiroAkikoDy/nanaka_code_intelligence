from __future__ import annotations

import os
from typing import Any

from mcp.server.fastmcp import FastMCP
from neo4j import GraphDatabase

mcp: FastMCP = FastMCP("code-graph")

NEO4J_DATABASE = os.environ.get("NEO4J_DATABASE", "nanaka-code-graph")

_driver: Any = None
_driver_initialized: bool = False


def _get_driver() -> Any:
    global _driver, _driver_initialized
    if _driver_initialized:
        return _driver
    _driver_initialized = True
    uri = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
    user = os.environ.get("NEO4J_USER", "neo4j")
    password = os.environ.get("NEO4J_PASSWORD")
    if not password:
        return None
    try:
        driver = GraphDatabase.driver(uri, auth=(user, password))
        driver.verify_connectivity()
        _driver = driver
    except Exception:
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
            "error": "Cannot connect to Neo4j. Run ingest_code_graph.py first.",
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
            "error": "Cannot connect to Neo4j. Run ingest_code_graph.py first.",
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
