from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from mcp_servers.code_graph_server import (
    get_call_graph,
    get_impact_analysis_graph,
    mcp,
    _get_driver,
    _reset_driver,
)


class TestGetImpactAnalysisGraphSuccess:
    @patch("mcp_servers.code_graph_server._get_driver")
    def test_returns_defines_and_impacted_files(self, mock_get_driver: MagicMock) -> None:
        mock_driver = MagicMock()
        mock_session = MagicMock()
        mock_driver.session.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_driver.session.return_value.__exit__ = MagicMock(return_value=False)
        mock_get_driver.return_value = mock_driver

        define_result = MagicMock()
        define_result.__iter__ = MagicMock(
            return_value=iter([{"sym_name": "my_func"}, {"sym_name": "MyClass"}])
        )

        impact_result = MagicMock()
        impact_result.__iter__ = MagicMock(
            return_value=iter(
                [
                    {"file": "path/to/other.py", "via_symbols": ["my_func"]},
                    {"file": "path/to/another.py", "via_symbols": ["MyClass"]},
                ]
            )
        )

        mock_session.run.side_effect = [define_result, impact_result]

        result = get_impact_analysis_graph("path/to/file.py")

        assert result["changed_file"] == "path/to/file.py"
        assert "my_func" in result["defines"]
        assert "MyClass" in result["defines"]
        assert result["count"] == 2
        assert result["source"] == "neo4j"
        assert len(result["impacted_files"]) == 2
        assert result["impacted_files"][0]["file"] == "path/to/other.py"
        assert "my_func" in result["impacted_files"][0]["via_symbols"]

    @patch("mcp_servers.code_graph_server._get_driver")
    def test_no_impacted_files(self, mock_get_driver: MagicMock) -> None:
        mock_driver = MagicMock()
        mock_session = MagicMock()
        mock_driver.session.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_driver.session.return_value.__exit__ = MagicMock(return_value=False)
        mock_get_driver.return_value = mock_driver

        define_result = MagicMock()
        define_result.__iter__ = MagicMock(return_value=iter([]))

        impact_result = MagicMock()
        impact_result.__iter__ = MagicMock(return_value=iter([]))

        mock_session.run.side_effect = [define_result, impact_result]

        result = get_impact_analysis_graph("isolated.py")

        assert result["changed_file"] == "isolated.py"
        assert result["defines"] == []
        assert result["impacted_files"] == []
        assert result["count"] == 0
        assert result["source"] == "neo4j"


class TestGetImpactAnalysisGraphError:
    @patch("mcp_servers.code_graph_server._get_driver")
    def test_neo4j_not_running(self, mock_get_driver: MagicMock) -> None:
        mock_get_driver.return_value = None

        result = get_impact_analysis_graph("path/to/file.py")

        assert result["changed_file"] == "path/to/file.py"
        assert result["source"] == "error"
        assert "error" in result
        assert "fallback" in result
        assert result["defines"] == []
        assert result["impacted_files"] == []
        assert result["count"] == 0


class TestGetCallGraphSuccess:
    @patch("mcp_servers.code_graph_server._get_driver")
    def test_returns_call_chain(self, mock_get_driver: MagicMock) -> None:
        mock_driver = MagicMock()
        mock_session = MagicMock()
        mock_driver.session.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_driver.session.return_value.__exit__ = MagicMock(return_value=False)
        mock_get_driver.return_value = mock_driver

        call_result = MagicMock()
        call_result.__iter__ = MagicMock(
            return_value=iter(
                [
                    {"from": "my_func", "to": "helper", "depth": 1},
                    {"from": "helper", "to": "util", "depth": 2},
                ]
            )
        )

        mock_session.run.return_value = call_result

        result = get_call_graph("my_func", depth=2)

        assert result["function"] == "my_func"
        assert result["depth"] == 2
        assert result["count"] == 2
        assert result["source"] == "neo4j"
        assert result["calls"][0] == {"from": "my_func", "to": "helper", "depth": 1}
        assert result["calls"][1] == {"from": "helper", "to": "util", "depth": 2}
        assert "note" in result

    @patch("mcp_servers.code_graph_server._get_driver")
    def test_no_calls(self, mock_get_driver: MagicMock) -> None:
        mock_driver = MagicMock()
        mock_session = MagicMock()
        mock_driver.session.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_driver.session.return_value.__exit__ = MagicMock(return_value=False)
        mock_get_driver.return_value = mock_driver

        call_result = MagicMock()
        call_result.__iter__ = MagicMock(return_value=iter([]))

        mock_session.run.return_value = call_result

        result = get_call_graph("leaf_func", depth=2)

        assert result["function"] == "leaf_func"
        assert result["calls"] == []
        assert result["count"] == 0
        assert result["source"] == "neo4j"


class TestGetCallGraphError:
    @patch("mcp_servers.code_graph_server._get_driver")
    def test_neo4j_not_running(self, mock_get_driver: MagicMock) -> None:
        mock_get_driver.return_value = None

        result = get_call_graph("my_func", depth=2)

        assert result["function"] == "my_func"
        assert result["depth"] == 2
        assert result["source"] == "error"
        assert "error" in result
        assert "fallback" in result
        assert result["calls"] == []
        assert result["count"] == 0


class TestGetCallGraphDepthValidation:
    @patch("mcp_servers.code_graph_server._get_driver")
    def test_depth_must_be_positive(self, mock_get_driver: MagicMock) -> None:
        mock_get_driver.return_value = MagicMock()

        result = get_call_graph("my_func", depth=0)

        assert result["source"] == "error"
        assert "error" in result

    @patch("mcp_servers.code_graph_server._get_driver")
    def test_depth_negative(self, mock_get_driver: MagicMock) -> None:
        mock_get_driver.return_value = MagicMock()

        result = get_call_graph("my_func", depth=-1)

        assert result["source"] == "error"
        assert "error" in result


class TestMcpServerTypeAnnotation:
    def test_mcp_has_type_annotation(self) -> None:
        from mcp.server.fastmcp import FastMCP

        assert isinstance(mcp, FastMCP)


class TestGetDriverReturnsNoneWhenNeo4jDown:
    def test_get_driver_returns_none_when_neo4j_down(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("NEO4J_URI", "bolt://localhost:9999")
        _reset_driver()
        result = _get_driver()
        assert result is None


class TestGetImpactAnalysisGraphNeo4jDown:
    def test_returns_error_dict_when_neo4j_down(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("NEO4J_URI", "bolt://localhost:9999")
        _reset_driver()
        result = get_impact_analysis_graph("test.py")
        assert "error" in result
        assert "fallback" in result
        assert result["source"] == "error"


class TestGetCallGraphNeo4jDown:
    def test_returns_error_dict_when_neo4j_down(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("NEO4J_URI", "bolt://localhost:9999")
        _reset_driver()
        result = get_call_graph("test_function")
        assert isinstance(result, dict)
        assert "error" in result
        assert "fallback" in result
        assert result["source"] == "error"


class TestDriverConnectionAttemptedWithEmptyPassword:
    def test_connection_attempted_even_without_password(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("NEO4J_PASSWORD", raising=False)
        _reset_driver()

        with patch("neo4j.GraphDatabase.driver", side_effect=Exception("Connection refused")) as mock_driver:
            result = _get_driver()

        mock_driver.assert_called_once()
        assert result is None
