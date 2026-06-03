from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest


class TestHybridSearchReturnKeys:
    def test_returns_graph_vector_hybrid_keys(self) -> None:
        from mcp_servers.code_intelligence_server import tool_hybrid_search

        mock_graph_refs = [
            {"file": "src/scheduler.py", "line": 10, "content": "generate_daily_script()"},
        ]
        mock_vector_results = [
            {"function": "generate_weekly_script", "file": "src/scheduler.py", "score": 0.91},
        ]

        with patch("mcp_servers.code_intelligence_server.find_references") as mock_find_refs, \
             patch("mcp_servers.code_intelligence_server.find_similar_code") as mock_find_similar:
            mock_find_refs.return_value = {
                "symbol": "generate_daily_script",
                "references": mock_graph_refs,
                "count": 1,
                "error": None,
            }
            mock_find_similar.return_value = mock_vector_results

            result = tool_hybrid_search("generate_daily_script", project_root=".")

            assert "query" in result
            assert "graph_results" in result
            assert "vector_results" in result
            assert "hybrid_results" in result
            assert "note" in result
            assert result["query"] == "generate_daily_script"


class TestReciprocalRankFusion:
    def test_rrf_score_formula(self) -> None:
        from mcp_servers.code_intelligence_server import _reciprocal_rank_fusion

        graph = [
            {"file": "src/a.py", "line": 1, "content": "foo"},
            {"file": "src/b.py", "line": 2, "content": "bar"},
        ]
        vector = [
            {"function": "baz", "file": "src/a.py", "score": 0.9},
        ]

        result = _reciprocal_rank_fusion(graph, vector, k=60)

        assert isinstance(result, list)
        assert len(result) > 0
        assert "file" in result[0]
        assert "rrf_score" in result[0]

        assert result[0]["file"] == "src/a.py"
        expected_score = round(1.0 / (60 + 0 + 1) + 1.0 / (60 + 0 + 1), 6)
        assert result[0]["rrf_score"] == expected_score

    def test_rrf_higher_score_ranks_first(self) -> None:
        from mcp_servers.code_intelligence_server import _reciprocal_rank_fusion

        graph = [
            {"file": "src/high.py", "line": 1, "content": "x"},
            {"file": "src/low.py", "line": 2, "content": "y"},
        ]
        vector = [
            {"function": "fn", "file": "src/high.py", "score": 0.95},
        ]

        result = _reciprocal_rank_fusion(graph, vector)

        high_entry = next(r for r in result if r["file"] == "src/high.py")
        low_entry = next(r for r in result if r["file"] == "src/low.py")
        assert high_entry["rrf_score"] > low_entry["rrf_score"]

    def test_rrf_max_five_results(self) -> None:
        from mcp_servers.code_intelligence_server import _reciprocal_rank_fusion

        graph = [{"file": f"src/f{i}.py", "line": i, "content": "x"} for i in range(10)]
        vector = [{"function": f"fn{i}", "file": f"src/v{i}.py", "score": 0.9} for i in range(10)]

        result = _reciprocal_rank_fusion(graph, vector)

        assert len(result) <= 5

    def test_rrf_exact_calculation(self) -> None:
        from mcp_servers.code_intelligence_server import _reciprocal_rank_fusion

        graph = [{"file": "src/a.py", "line": 1, "content": "x"}]
        vector = [{"function": "fn", "file": "src/b.py", "score": 0.9}]

        result = _reciprocal_rank_fusion(graph, vector, k=60)

        a_entry = next(r for r in result if r["file"] == "src/a.py")
        b_entry = next(r for r in result if r["file"] == "src/b.py")
        assert a_entry["rrf_score"] == round(1.0 / (60 + 0 + 1), 6)
        assert b_entry["rrf_score"] == round(1.0 / (60 + 0 + 1), 6)


class TestHybridSearchGraphOnlyFallback:
    def test_neo4j_unavailable_uses_graph_only(self) -> None:
        from mcp_servers.code_intelligence_server import tool_hybrid_search

        mock_graph_refs = [
            {"file": "src/scheduler.py", "line": 5, "content": "generate_daily_script()"},
        ]

        with patch("mcp_servers.code_intelligence_server.find_references") as mock_find_refs, \
             patch("mcp_servers.code_intelligence_server.find_similar_code") as mock_find_similar:
            mock_find_refs.return_value = {
                "symbol": "generate_daily_script",
                "references": mock_graph_refs,
                "count": 1,
                "error": None,
            }
            mock_find_similar.return_value = [
                {"error": "Cannot connect to Neo4j or vector index not found."}
            ]

            result = tool_hybrid_search("generate_daily_script", project_root=".")

            assert result["vector_results"] == []
            assert result["graph_results"] == mock_graph_refs
            assert len(result["hybrid_results"]) > 0
            assert "graph_resultsのみでRRF" in result["note"]

    def test_empty_results_still_returns_structure(self) -> None:
        from mcp_servers.code_intelligence_server import tool_hybrid_search

        with patch("mcp_servers.code_intelligence_server.find_references") as mock_find_refs, \
             patch("mcp_servers.code_intelligence_server.find_similar_code") as mock_find_similar:
            mock_find_refs.return_value = {
                "symbol": "nonexistent",
                "references": [],
                "count": 0,
                "error": None,
            }
            mock_find_similar.return_value = [
                {"error": "Cannot connect to Neo4j or vector index not found."}
            ]

            result = tool_hybrid_search("nonexistent", project_root=".")

            assert result["query"] == "nonexistent"
            assert result["graph_results"] == []
            assert result["vector_results"] == []
            assert result["hybrid_results"] == []


class TestHybridSearchSuccessNote:
    def test_success_note_when_vector_available(self) -> None:
        from mcp_servers.code_intelligence_server import tool_hybrid_search

        with patch("mcp_servers.code_intelligence_server.find_references") as mock_find_refs, \
             patch("mcp_servers.code_intelligence_server.find_similar_code") as mock_find_similar:
            mock_find_refs.return_value = {
                "symbol": "test_fn",
                "references": [{"file": "src/a.py", "line": 1, "content": "test_fn"}],
                "count": 1,
                "error": None,
            }
            mock_find_similar.return_value = [
                {"function": "test_fn", "file": "src/a.py", "score": 0.95},
            ]

            result = tool_hybrid_search("test_fn", project_root=".")

            assert "RRF統合済み" in result["note"]


class TestHybridSearchTypeAnnotation:
    def test_return_type_annotation(self) -> None:
        from mcp_servers.code_intelligence_server import tool_hybrid_search

        import inspect
        sig = inspect.signature(tool_hybrid_search)
        ann = sig.return_annotation
        assert ann == "dict[str, Any]" or ann == dict[str, Any]
