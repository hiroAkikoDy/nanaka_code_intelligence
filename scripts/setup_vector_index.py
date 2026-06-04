from __future__ import annotations

import os
import sys
from typing import Any

from neo4j import GraphDatabase

NEO4J_DATABASE = os.environ.get("NEO4J_DATABASE", "nanaka-code-graph")


def create_vector_index(driver: Any) -> None:
    with driver.session(database=NEO4J_DATABASE) as session:
        session.run(
            """
            CREATE VECTOR INDEX code_embeddings
            IF NOT EXISTS
            FOR (f:Function)
            ON f.embedding
            OPTIONS {
                indexConfig: {
                    `vector.dimensions`: 384,
                    `vector.similarity_function`: 'cosine'
                }
            }
            """
        )
    print("Vector index 'code_embeddings' created (or already exists).")


def main() -> None:
    uri = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
    user = os.environ.get("NEO4J_USER", "neo4j")
    password = os.environ.get("NEO4J_PASSWORD")
    if not password:
        print(
            "Error: NEO4J_PASSWORD environment variable is required.",
            file=sys.stderr,
        )
        sys.exit(1)

    try:
        driver = GraphDatabase.driver(uri, auth=(user, password))
        driver.verify_connectivity()
        create_vector_index(driver)
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)
    finally:
        driver.close()


if __name__ == "__main__":
    main()
