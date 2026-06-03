import ast
import textwrap
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from scripts.ingest_code_graph import (
    build_arg_parser,
    create_neo4j_driver,
    find_python_files,
    ingest_project,
    parse_python_file,
)


class TestParsePythonFile:
    def test_parse_simple_function(self, tmp_path: Path) -> None:
        code = textwrap.dedent("""\
            def hello():
                pass
        """)
        fp = tmp_path / "sample.py"
        fp.write_text(code, encoding="utf-8")

        result = parse_python_file(fp)

        assert len(result["functions"]) == 1
        assert result["functions"][0]["name"] == "hello"
        assert result["functions"][0]["line"] == 1

    def test_parse_class(self, tmp_path: Path) -> None:
        code = textwrap.dedent("""\
            class Foo:
                def bar(self):
                    pass
        """)
        fp = tmp_path / "cls.py"
        fp.write_text(code, encoding="utf-8")

        result = parse_python_file(fp)

        assert len(result["classes"]) == 1
        assert result["classes"][0]["name"] == "Foo"
        assert result["classes"][0]["line"] == 1

    def test_parse_imports(self, tmp_path: Path) -> None:
        code = textwrap.dedent("""\
            import os
            from pathlib import Path
        """)
        fp = tmp_path / "imp.py"
        fp.write_text(code, encoding="utf-8")

        result = parse_python_file(fp)

        assert len(result["imports"]) == 2
        names = [i["name"] for i in result["imports"]]
        assert "os" in names
        assert "pathlib.Path" in names

    def test_parse_function_calls(self, tmp_path: Path) -> None:
        code = textwrap.dedent("""\
            def foo():
                bar()

            def bar():
                baz()
        """)
        fp = tmp_path / "calls.py"
        fp.write_text(code, encoding="utf-8")

        result = parse_python_file(fp)

        foo = next(f for f in result["functions"] if f["name"] == "foo")
        assert "bar" in foo["calls"]

        bar = next(f for f in result["functions"] if f["name"] == "bar")
        assert "baz" in bar["calls"]

    def test_parse_nested_calls_inside_class(self, tmp_path: Path) -> None:
        code = textwrap.dedent("""\
            class MyService:
                def process(self):
                    self._validate()
                    self._save()

                def _validate(self):
                    pass

                def _save(self):
                    pass
        """)
        fp = tmp_path / "svc.py"
        fp.write_text(code, encoding="utf-8")

        result = parse_python_file(fp)

        process = next(f for f in result["functions"] if f["name"] == "process")
        assert "_validate" in process["calls"]
        assert "_save" in process["calls"]

    def test_parse_empty_file(self, tmp_path: Path) -> None:
        fp = tmp_path / "empty.py"
        fp.write_text("", encoding="utf-8")

        result = parse_python_file(fp)

        assert result["functions"] == []
        assert result["classes"] == []
        assert result["imports"] == []

    def test_parse_syntax_error_file(self, tmp_path: Path) -> None:
        fp = tmp_path / "bad.py"
        fp.write_text("def (", encoding="utf-8")

        result = parse_python_file(fp)

        assert result["functions"] == []
        assert result["classes"] == []
        assert result["imports"] == []


class TestFindPythonFiles:
    def test_finds_py_files(self, tmp_path: Path) -> None:
        (tmp_path / "a.py").write_text("pass", encoding="utf-8")
        (tmp_path / "b.py").write_text("pass", encoding="utf-8")
        (tmp_path / "c.txt").write_text("not python", encoding="utf-8")

        result = find_python_files(tmp_path)

        names = [f.name for f in result]
        assert "a.py" in names
        assert "b.py" in names
        assert "c.txt" not in names

    def test_recursive_search(self, tmp_path: Path) -> None:
        sub = tmp_path / "pkg"
        sub.mkdir()
        (sub / "mod.py").write_text("pass", encoding="utf-8")

        result = find_python_files(tmp_path)

        assert any(f.name == "mod.py" for f in result)

    def test_skips_hidden_dirs(self, tmp_path: Path) -> None:
        hidden = tmp_path / ".hidden"
        hidden.mkdir()
        (hidden / "secret.py").write_text("pass", encoding="utf-8")
        (tmp_path / "visible.py").write_text("pass", encoding="utf-8")

        result = find_python_files(tmp_path)

        names = [f.name for f in result]
        assert "visible.py" in names
        assert "secret.py" not in names

    def test_nonexistent_root_raises(self) -> None:
        with pytest.raises(FileNotFoundError):
            find_python_files(Path("/nonexistent/path/abc123"))


class TestIngestProject:
    def test_ingest_creates_nodes_and_relations(self, tmp_path: Path) -> None:
        code = textwrap.dedent("""\
            import os

            def hello():
                world()

            def world():
                pass
        """)
        (tmp_path / "app.py").write_text(code, encoding="utf-8")

        mock_driver = MagicMock()
        mock_session = MagicMock()
        mock_driver.session.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_driver.session.return_value.__exit__ = MagicMock(return_value=False)

        stats = ingest_project(tmp_path, mock_driver)

        assert stats["files"] == 1
        assert stats["functions"] == 2
        assert stats["classes"] == 0

        assert mock_session.run.called

    def test_ingest_clear_option(self, tmp_path: Path) -> None:
        (tmp_path / "a.py").write_text("pass", encoding="utf-8")

        mock_driver = MagicMock()
        mock_session = MagicMock()
        mock_driver.session.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_driver.session.return_value.__exit__ = MagicMock(return_value=False)

        ingest_project(tmp_path, mock_driver, clear=True)

        first_call_query = mock_session.run.call_args_list[0][0][0]
        assert "MATCH" in first_call_query or "DETACH" in first_call_query


class TestBuildArgParser:
    def test_default_values(self) -> None:
        parser = build_arg_parser()
        args = parser.parse_args(["--project-root", "/tmp/proj", "--neo4j-pass", "pw"])

        assert args.project_root == Path("/tmp/proj")
        assert args.neo4j_uri == "bolt://localhost:7687"
        assert args.neo4j_user == "neo4j"
        assert args.neo4j_pass == "pw"
        assert args.clear is False

    def test_password_from_env(self) -> None:
        parser = build_arg_parser()
        with patch.dict("os.environ", {"NEO4J_PASSWORD": "envpw"}):
            args = parser.parse_args(["--project-root", "/tmp/proj"])
            assert args.neo4j_pass == "envpw"

    def test_missing_password_and_env_fails(self) -> None:
        parser = build_arg_parser()
        with patch.dict("os.environ", {}, clear=True):
            with pytest.raises(SystemExit):
                parser.parse_args(["--project-root", "/tmp/proj"])


class TestCreateNeo4jDriver:
    def test_graceful_error_on_connection_failure(self) -> None:
        with patch("scripts.ingest_code_graph.GraphDatabase") as mock_gdb:
            mock_gdb.driver.side_effect = Exception("Connection refused")
            with pytest.raises(SystemExit):
                create_neo4j_driver("bolt://localhost:7687", "neo4j", "pw")
