from __future__ import annotations

import textwrap
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest


class TestSetupVectorIndex:
    def test_create_vector_index_calls_session_run(self) -> None:
        from scripts.setup_vector_index import create_vector_index

        mock_driver = MagicMock()
        mock_session = MagicMock()
        mock_driver.session.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_driver.session.return_value.__exit__ = MagicMock(return_value=False)

        create_vector_index(mock_driver)

        mock_session.run.assert_called_once()
        query = mock_session.run.call_args[0][0]
        assert "VECTOR INDEX" in query
        assert "code_embeddings" in query

    def test_create_vector_index_dimension_384(self) -> None:
        from scripts.setup_vector_index import create_vector_index

        mock_driver = MagicMock()
        mock_session = MagicMock()
        mock_driver.session.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_driver.session.return_value.__exit__ = MagicMock(return_value=False)

        create_vector_index(mock_driver)

        query = mock_session.run.call_args[0][0]
        assert "384" in query
        assert "cosine" in query


class TestFindSimilarCode:
    def test_returns_list_of_dicts(self) -> None:
        from mcp_servers.code_intelligence_server import find_similar_code

        mock_records = [
            {"function": "classify_comment", "file": "src/classifier.py", "score": 0.92},
            {"function": "detect_sentiment", "file": "src/analyzer.py", "score": 0.87},
        ]

        mock_embed = MagicMock()
        mock_embed.encode.return_value.tolist.return_value = [0.1] * 384

        with patch("mcp_servers.code_intelligence_server._get_neo4j_driver") as mock_get_driver, \
             patch("mcp_servers.code_intelligence_server._get_embed_model", return_value=mock_embed):
            mock_driver = MagicMock()
            mock_session = MagicMock()
            mock_driver.session.return_value.__enter__ = MagicMock(return_value=mock_session)
            mock_driver.session.return_value.__exit__ = MagicMock(return_value=False)
            mock_get_driver.return_value = mock_driver

            mock_session.run.return_value = [mock_records[0], mock_records[1]]

            result = find_similar_code("classify text")

            assert isinstance(result, list)
            assert len(result) == 2
            assert result[0]["function"] == "classify_comment"
            assert result[0]["score"] == 0.92
            assert result[1]["function"] == "detect_sentiment"

    def test_neo4j_not_running_returns_error(self) -> None:
        from mcp_servers.code_intelligence_server import find_similar_code

        with patch("mcp_servers.code_intelligence_server._get_neo4j_driver", return_value=None):
            result = find_similar_code("some query")

            assert isinstance(result, list)
            assert len(result) == 1
            assert "error" in result[0]
            assert "Cannot connect to Neo4j" in result[0]["error"] or "vector index not found" in result[0]["error"]

    def test_top_k_passed_to_cypher(self) -> None:
        from mcp_servers.code_intelligence_server import find_similar_code

        mock_embed = MagicMock()
        mock_embed.encode.return_value.tolist.return_value = [0.1] * 384

        with patch("mcp_servers.code_intelligence_server._get_neo4j_driver") as mock_get_driver, \
             patch("mcp_servers.code_intelligence_server._get_embed_model", return_value=mock_embed):
            mock_driver = MagicMock()
            mock_session = MagicMock()
            mock_driver.session.return_value.__enter__ = MagicMock(return_value=mock_session)
            mock_driver.session.return_value.__exit__ = MagicMock(return_value=False)
            mock_get_driver.return_value = mock_driver

            mock_session.run.return_value = []

            find_similar_code("test query", top_k=10)

            call_kwargs = mock_session.run.call_args[1]
            assert call_kwargs["top_k"] == 10
            assert "embedding" in call_kwargs
            assert call_kwargs["embedding"] == [0.1] * 384

    def test_empty_result_returns_empty_list(self) -> None:
        from mcp_servers.code_intelligence_server import find_similar_code

        mock_embed = MagicMock()
        mock_embed.encode.return_value.tolist.return_value = [0.1] * 384

        with patch("mcp_servers.code_intelligence_server._get_neo4j_driver") as mock_get_driver, \
             patch("mcp_servers.code_intelligence_server._get_embed_model", return_value=mock_embed):
            mock_driver = MagicMock()
            mock_session = MagicMock()
            mock_driver.session.return_value.__enter__ = MagicMock(return_value=mock_session)
            mock_driver.session.return_value.__exit__ = MagicMock(return_value=False)
            mock_get_driver.return_value = mock_driver

            mock_session.run.return_value = []

            result = find_similar_code("obscure query")

            assert result == []

    def test_return_type_annotation(self) -> None:
        from mcp_servers.code_intelligence_server import find_similar_code

        import inspect
        sig = inspect.signature(find_similar_code)
        ann = sig.return_annotation
        assert ann == "list[dict[str, Any]]" or ann == list[dict[str, Any]]


class TestIngestProjectWithEmbeddings:
    def test_function_nodes_get_embedding_property(self, tmp_path: Path) -> None:
        from scripts.ingest_code_graph import ingest_project

        code = textwrap.dedent("""\
            def hello():
                world()
        """)
        (tmp_path / "app.py").write_text(code, encoding="utf-8")

        mock_driver = MagicMock()
        mock_session = MagicMock()
        mock_driver.session.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_driver.session.return_value.__exit__ = MagicMock(return_value=False)

        mock_model = MagicMock()
        mock_model.encode.return_value.tolist.return_value = [0.1] * 384

        with patch("scripts.ingest_code_graph._get_model", return_value=mock_model):
            stats = ingest_project(tmp_path, mock_driver)

            assert stats["functions"] == 1
            merge_calls = [
                c for c in mock_session.run.call_args_list
                if "MERGE (fn:Function" in str(c)
            ]
            assert len(merge_calls) > 0
            kwargs = merge_calls[0][1]
            assert "embedding" in kwargs
            assert kwargs["embedding"] == [0.1] * 384


class TestGetNeo4jDriver:
    def test_returns_none_when_no_password(self) -> None:
        import mcp_servers.code_intelligence_server as mod

        original_init = mod._neo4j_driver_initialized
        original_driver = mod._neo4j_driver
        mod._neo4j_driver_initialized = False
        mod._neo4j_driver = None
        try:
            with patch.dict("os.environ", {}, clear=True):
                result = mod._get_neo4j_driver()
                assert result is None
        finally:
            mod._neo4j_driver_initialized = original_init
            mod._neo4j_driver = original_driver

    def test_returns_driver_on_success(self) -> None:
        import mcp_servers.code_intelligence_server as mod

        original_init = mod._neo4j_driver_initialized
        original_driver = mod._neo4j_driver
        mod._neo4j_driver_initialized = False
        mod._neo4j_driver = None
        try:
            with patch.dict("os.environ", {"NEO4J_PASSWORD": "test", "NEO4J_URI": "bolt://localhost:7687", "NEO4J_USER": "neo4j"}), \
                 patch.object(mod, "GraphDatabase") as mock_gdb:
                mock_driver = MagicMock()
                mock_gdb.driver.return_value = mock_driver

                result = mod._get_neo4j_driver()

                assert result is mock_driver
                mock_gdb.driver.assert_called_once_with(
                    "bolt://localhost:7687",
                    auth=("neo4j", "test"),
                )
        finally:
            mod._neo4j_driver_initialized = original_init
            mod._neo4j_driver = original_driver
