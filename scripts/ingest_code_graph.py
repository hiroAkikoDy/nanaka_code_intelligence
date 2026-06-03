from __future__ import annotations

import argparse
import ast
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from neo4j import GraphDatabase

_model: Any = None


def _get_model() -> Any:
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer("all-MiniLM-L6-v2")
    return _model


class _CallVisitor(ast.NodeVisitor):
    def __init__(self) -> None:
        self.calls: list[str] = []

    def visit_Call(self, node: ast.Call) -> None:
        if isinstance(node.func, ast.Name):
            self.calls.append(node.func.id)
        elif isinstance(node.func, ast.Attribute):
            self.calls.append(node.func.attr)
        self.generic_visit(node)


class _ImportVisitor(ast.NodeVisitor):
    def __init__(self) -> None:
        self.imports: list[str] = []

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            self.imports.append(alias.name)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        module = node.module or ""
        for alias in node.names:
            self.imports.append(f"{module}.{alias.name}")


def parse_python_file(file_path: Path) -> dict[str, Any]:
    try:
        source = file_path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(file_path))
    except (SyntaxError, UnicodeDecodeError):
        return {"functions": [], "classes": [], "imports": []}

    imports: list[dict[str, Any]] = []
    functions: list[dict[str, Any]] = []
    classes: list[dict[str, Any]] = []

    import_visitor = _ImportVisitor()
    import_visitor.visit(tree)
    for name in import_visitor.imports:
        imports.append({"name": name, "file": str(file_path)})

    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.FunctionDef) or isinstance(node, ast.AsyncFunctionDef):
            call_visitor = _CallVisitor()
            call_visitor.visit(node)
            functions.append({
                "name": node.name,
                "file": str(file_path),
                "line": node.lineno,
                "calls": call_visitor.calls,
            })
        elif isinstance(node, ast.ClassDef):
            class_methods: list[dict[str, Any]] = []
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    call_visitor = _CallVisitor()
                    call_visitor.visit(item)
                    class_methods.append({
                        "name": item.name,
                        "file": str(file_path),
                        "line": item.lineno,
                        "calls": call_visitor.calls,
                    })
            classes.append({
                "name": node.name,
                "file": str(file_path),
                "line": node.lineno,
            })
            functions.extend(class_methods)

    return {"functions": functions, "classes": classes, "imports": imports}


def find_python_files(project_root: Path) -> list[Path]:
    if not project_root.exists():
        raise FileNotFoundError(f"Project root not found: {project_root}")

    result: list[Path] = []
    for path in project_root.rglob("*.py"):
        parts = path.relative_to(project_root).parts
        if any(part.startswith(".") for part in parts):
            continue
        result.append(path)
    return sorted(result)


def ingest_project(
    project_root: Path,
    driver: Any,
    clear: bool = False,
) -> dict[str, int]:
    py_files = find_python_files(project_root)
    total_functions: int = 0
    total_classes: int = 0

    with driver.session() as session:
        if clear:
            session.run("MATCH (n) DETACH DELETE n")

        for fp in py_files:
            parsed = parse_python_file(fp)
            rel_path = str(fp)

            session.run(
                "MERGE (f:File {path: $path}) SET f.name = $name",
                path=rel_path,
                name=fp.name,
            )

            for func in parsed["functions"]:
                total_functions += 1
                embedding = _get_model().encode(
                    f"{func['name']} {func.get('calls', [])}"
                ).tolist()
                session.run(
                    """
                    MERGE (fn:Function {name: $name, file: $file, line: $line})
                    SET fn.embedding = $embedding
                    WITH fn
                    MATCH (f:File {path: $file})
                    MERGE (f)-[:DEFINES]->(fn)
                    """,
                    name=func["name"],
                    file=func["file"],
                    line=func["line"],
                    embedding=embedding,
                )
                for called in func["calls"]:
                    session.run(
                        """
                        MATCH (caller:Function {name: $caller_name, file: $caller_file})
                        MERGE (callee:Function {name: $callee_name})
                        MERGE (caller)-[:CALLS]->(callee)
                        """,
                        caller_name=func["name"],
                        caller_file=func["file"],
                        callee_name=called,
                    )

            for cls in parsed["classes"]:
                total_classes += 1
                session.run(
                    """
                    MERGE (c:Class {name: $name, file: $file, line: $line})
                    WITH c
                    MATCH (f:File {path: $file})
                    MERGE (f)-[:DEFINES]->(c)
                    """,
                    name=cls["name"],
                    file=cls["file"],
                    line=cls["line"],
                )

            for imp in parsed["imports"]:
                session.run(
                    """
                    MERGE (i:Import {name: $name, file: $file})
                    WITH i
                    MATCH (f:File {path: $file})
                    MERGE (f)-[:IMPORTS]->(i)
                    """,
                    name=imp["name"],
                    file=imp["file"],
                )

    return {
        "files": len(py_files),
        "functions": total_functions,
        "classes": total_classes,
    }


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Ingest Python code into a Neo4j graph"
    )
    parser.add_argument(
        "--project-root",
        type=Path,
        required=True,
        help="Root directory of the Python project to ingest",
    )
    parser.add_argument(
        "--neo4j-uri",
        default="bolt://localhost:7687",
        help="Neo4j bolt URI (default: bolt://localhost:7687)",
    )
    parser.add_argument(
        "--neo4j-user",
        default="neo4j",
        help="Neo4j username (default: neo4j)",
    )
    parser.add_argument(
        "--neo4j-pass",
        default=None,
        help="Neo4j password (or set NEO4J_PASSWORD env var)",
    )
    parser.add_argument(
        "--clear",
        action="store_true",
        help="Clear existing graph before ingesting",
    )

    class _ValidateAction(argparse.Action):
        def __call__(
            self,
            parser: argparse.ArgumentParser,
            namespace: argparse.Namespace,
            values: Any,
            option_string: str | None = None,
        ) -> None:
            if values is None:
                parser.error(
                    "Neo4j password is required. "
                    "Use --neo4j-pass or set NEO4J_PASSWORD environment variable."
                )
            setattr(namespace, self.dest, values)

    original_parse_args = parser.parse_args

    def _wrapped_parse_args(args: Any = None, namespace: Any = None) -> Any:
        ns = original_parse_args(args, namespace)
        if ns.neo4j_pass is None:
            env_pass = os.environ.get("NEO4J_PASSWORD")
            if env_pass is not None:
                ns.neo4j_pass = env_pass
            else:
                parser.error(
                    "Neo4j password is required. "
                    "Use --neo4j-pass or set NEO4J_PASSWORD environment variable."
                )
        return ns

    parser.parse_args = _wrapped_parse_args  # type: ignore[assignment]
    return parser


def create_neo4j_driver(uri: str, user: str, password: str) -> Any:
    try:
        driver = GraphDatabase.driver(uri, auth=(user, password))
        driver.verify_connectivity()
        return driver
    except Exception as exc:
        print(
            f"Error: Cannot connect to Neo4j at {uri}.\n"
            f"  Reason: {exc}\n"
            f"  Make sure Neo4j is running and credentials are correct.",
            file=sys.stderr,
        )
        sys.exit(1)


def update_incrementally(
    project_root: str = ".",
    driver: Any = None,
) -> dict[str, Any]:
    result = subprocess.run(
        ["git", "diff", "--name-only", "HEAD~1"],
        capture_output=True,
        text=True,
        cwd=project_root,
    )
    if result.returncode != 0:
        return {"updated_files": [], "skipped": [], "error": "Not a git repository or git command failed."}

    changed_py = [f for f in result.stdout.splitlines() if f.endswith(".py")]
    if not changed_py:
        return {"updated_files": [], "skipped": [], "error": None}

    if driver is None:
        uri = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
        user = os.environ.get("NEO4J_USER", "neo4j")
        password = os.environ.get("NEO4J_PASSWORD", "")
        try:
            driver = create_neo4j_driver(uri, user, password)
        except Exception:
            return {
                "updated_files": [],
                "skipped": [],
                "error": "Cannot connect to Neo4j. Run ingest_code_graph.py first.",
            }

    updated: list[str] = []
    root = Path(project_root)

    with driver.session() as session:
        for rel_path in changed_py:
            fp = root / rel_path
            session.run(
                "MATCH (f:File {path: $path}) DETACH DELETE f",
                path=rel_path,
            )

            parsed = parse_python_file(fp)

            session.run(
                "MERGE (f:File {path: $path}) SET f.name = $name",
                path=rel_path,
                name=fp.name,
            )

            for func in parsed["functions"]:
                session.run(
                    """
                    MERGE (fn:Function {name: $name, file: $file, line: $line})
                    WITH fn
                    MATCH (f:File {path: $file})
                    MERGE (f)-[:DEFINES]->(fn)
                    """,
                    name=func["name"],
                    file=func["file"],
                    line=func["line"],
                )
                for called in func["calls"]:
                    session.run(
                        """
                        MATCH (caller:Function {name: $caller_name, file: $caller_file})
                        MERGE (callee:Function {name: $callee_name})
                        MERGE (caller)-[:CALLS]->(callee)
                        """,
                        caller_name=func["name"],
                        caller_file=func["file"],
                        callee_name=called,
                    )

            for cls in parsed["classes"]:
                session.run(
                    """
                    MERGE (c:Class {name: $name, file: $file, line: $line})
                    WITH c
                    MATCH (f:File {path: $file})
                    MERGE (f)-[:DEFINES]->(c)
                    """,
                    name=cls["name"],
                    file=cls["file"],
                    line=cls["line"],
                )

            for imp in parsed["imports"]:
                session.run(
                    """
                    MERGE (i:Import {name: $name, file: $file})
                    WITH i
                    MATCH (f:File {path: $file})
                    MERGE (f)-[:IMPORTS]->(i)
                    """,
                    name=imp["name"],
                    file=imp["file"],
                )

            updated.append(rel_path)

    return {"updated_files": updated, "skipped": [], "error": None}


def main() -> None:
    parser = build_arg_parser()
    args = parser.parse_args()

    driver = create_neo4j_driver(args.neo4j_uri, args.neo4j_user, args.neo4j_pass)
    try:
        stats = ingest_project(args.project_root, driver, clear=args.clear)
        print(
            f"Ingested {stats['files']} files, "
            f"{stats['functions']} functions, "
            f"{stats['classes']} classes into Neo4j."
        )
    finally:
        driver.close()


if __name__ == "__main__":
    main()
