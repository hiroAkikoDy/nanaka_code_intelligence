from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from scripts.ingest_code_graph import update_incrementally


class TestGitRepositoryOutside:
    def test_not_git_repo(self) -> None:
        with patch("scripts.ingest_code_graph.subprocess") as mock_subprocess:
            mock_result = MagicMock()
            mock_result.returncode = 128
            mock_result.stdout = ""
            mock_subprocess.run.return_value = mock_result
            result = update_incrementally(project_root="/nonexistent")
        assert result["updated_files"] == []
        assert result["skipped"] == []
        assert result["error"] == "Not a git repository or git command failed."


class TestNoChangedPythonFiles:
    def test_no_py_files_changed(self) -> None:
        with patch("scripts.ingest_code_graph.subprocess") as mock_subprocess:
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = "README.md\ndata.json\n"
            mock_subprocess.run.return_value = mock_result
            result = update_incrementally(project_root=".")
        assert result["updated_files"] == []
        assert result["skipped"] == []
        assert result["error"] is None


class TestChangedPythonFilesExist:
    def test_updated_files_returned(self) -> None:
        mock_driver = MagicMock()
        mock_session = MagicMock()
        mock_driver.session.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_driver.session.return_value.__exit__ = MagicMock(return_value=False)

        with patch("scripts.ingest_code_graph.subprocess") as mock_subprocess:
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = "src/a.py\nsrc/b.py\n"
            mock_subprocess.run.return_value = mock_result

            with patch(
                "scripts.ingest_code_graph.parse_python_file",
                return_value={"functions": [], "classes": [], "imports": []},
            ):
                result = update_incrementally(
                    project_root=".", driver=mock_driver
                )

        assert "src/a.py" in result["updated_files"]
        assert "src/b.py" in result["updated_files"]
        assert result["error"] is None


class TestNeo4jNotRunning:
    def test_neo4j_connection_failure(self) -> None:
        with patch("scripts.ingest_code_graph.subprocess") as mock_subprocess:
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = "src/a.py\n"
            mock_subprocess.run.return_value = mock_result

            with patch(
                "scripts.ingest_code_graph.create_neo4j_driver",
                side_effect=Exception("Connection refused"),
            ):
                result = update_incrementally(project_root=".")

        assert result["updated_files"] == []
        assert result["skipped"] == []
        assert "Cannot connect to Neo4j" in result["error"]


class TestDetachDeleteBeforeReingest:
    def test_old_nodes_deleted_before_reingest(self) -> None:
        mock_driver = MagicMock()
        mock_session = MagicMock()
        mock_driver.session.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_driver.session.return_value.__exit__ = MagicMock(return_value=False)

        with patch("scripts.ingest_code_graph.subprocess") as mock_subprocess:
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = "src/a.py\n"
            mock_subprocess.run.return_value = mock_result

            with patch(
                "scripts.ingest_code_graph.parse_python_file",
                return_value={"functions": [], "classes": [], "imports": []},
            ):
                update_incrementally(project_root=".", driver=mock_driver)

        detach_calls = [
            c
            for c in mock_session.run.call_args_list
            if "DETACH DELETE" in str(c)
        ]
        assert len(detach_calls) >= 1


class TestDriverFromEnvironment:
    def test_driver_created_from_env_when_none(self) -> None:
        mock_driver = MagicMock()
        mock_session = MagicMock()
        mock_driver.session.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_driver.session.return_value.__exit__ = MagicMock(return_value=False)

        with patch("scripts.ingest_code_graph.subprocess") as mock_subprocess:
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = "src/x.py\n"
            mock_subprocess.run.return_value = mock_result

            with patch(
                "scripts.ingest_code_graph.parse_python_file",
                return_value={"functions": [], "classes": [], "imports": []},
            ):
                with patch(
                    "scripts.ingest_code_graph.create_neo4j_driver",
                    return_value=mock_driver,
                ) as mock_create:
                    with patch.dict(
                        "os.environ",
                        {
                            "NEO4J_URI": "bolt://localhost:7687",
                            "NEO4J_USER": "neo4j",
                            "NEO4J_PASSWORD": "test",
                        },
                    ):
                        result = update_incrementally(project_root=".")

        mock_create.assert_called_once_with(
            "bolt://localhost:7687", "neo4j", "test"
        )
        assert result["updated_files"] == ["src/x.py"]


class TestNonPyFilesSkipped:
    def test_only_py_files_processed(self) -> None:
        mock_driver = MagicMock()
        mock_session = MagicMock()
        mock_driver.session.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_driver.session.return_value.__exit__ = MagicMock(return_value=False)

        with patch("scripts.ingest_code_graph.subprocess") as mock_subprocess:
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = "src/a.py\nREADME.md\nsrc/b.txt\n"
            mock_subprocess.run.return_value = mock_result

            with patch(
                "scripts.ingest_code_graph.parse_python_file",
                return_value={"functions": [], "classes": [], "imports": []},
            ):
                result = update_incrementally(
                    project_root=".", driver=mock_driver
                )

        assert result["updated_files"] == ["src/a.py"]
        assert result["error"] is None


class TestFunctionsAndClassesReingested:
    def test_functions_and_classes_merged(self) -> None:
        mock_driver = MagicMock()
        mock_session = MagicMock()
        mock_driver.session.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_driver.session.return_value.__exit__ = MagicMock(return_value=False)

        parsed = {
            "functions": [
                {"name": "foo", "file": "src/a.py", "line": 1, "calls": []},
            ],
            "classes": [
                {"name": "Bar", "file": "src/a.py", "line": 5},
            ],
            "imports": [
                {"name": "os", "file": "src/a.py"},
            ],
        }

        with patch("scripts.ingest_code_graph.subprocess") as mock_subprocess:
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = "src/a.py\n"
            mock_subprocess.run.return_value = mock_result

            with patch(
                "scripts.ingest_code_graph.parse_python_file",
                return_value=parsed,
            ):
                result = update_incrementally(
                    project_root=".", driver=mock_driver
                )

        assert result["updated_files"] == ["src/a.py"]
        all_queries = [str(c) for c in mock_session.run.call_args_list]
        assert any("MERGE (f:File" in q for q in all_queries)
        assert any("MERGE (fn:Function" in q for q in all_queries)
        assert any("MERGE (c:Class" in q for q in all_queries)
        assert any("MERGE (i:Import" in q for q in all_queries)
