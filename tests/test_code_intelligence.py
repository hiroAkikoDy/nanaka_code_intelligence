import os
import textwrap
import tempfile
from pathlib import Path

import pytest

from mcp_servers.code_intelligence_server import (
    get_file_structure,
    find_references,
    get_impact_analysis,
)


@pytest.fixture
def sample_project(tmp_path: Path) -> Path:
    mod_py = tmp_path / "module_a.py"
    mod_py.write_text(
        textwrap.dedent(
            """\
            import os
            import sys
            from pathlib import Path

            def greet(name: str) -> str:
                return f"Hello {name}"

            def farewell(name: str) -> str:
                return f"Bye {name}"

            class MyClass:
                def __init__(self, value: int) -> None:
                    self.value = value

                def double(self) -> int:
                    return self.value * 2
            """
        ),
        encoding="utf-8",
    )

    consumer_py = tmp_path / "consumer.py"
    consumer_py.write_text(
        textwrap.dedent(
            """\
            from module_a import greet, MyClass

            def run() -> None:
                msg = greet("world")
                obj = MyClass(10)
                print(obj.double())
            """
        ),
        encoding="utf-8",
    )

    return tmp_path


class TestGetFileStructure:
    def test_parses_imports_classes_functions(self, sample_project: Path) -> None:
        result: dict = get_file_structure(str(sample_project / "module_a.py"))
        assert result["file"] == str(sample_project / "module_a.py")
        assert "os" in result["imports"]
        assert "sys" in result["imports"]
        assert "MyClass" in result["classes"]
        assert "greet" in result["functions"]
        assert "farewell" in result["functions"]
        assert result["error"] is None

    def test_nonexistent_file_returns_error(self) -> None:
        result: dict = get_file_structure("/nonexistent/path/file.py")
        assert result["error"] is not None
        assert isinstance(result["error"], str)

    def test_empty_file_returns_empty_lists(self, tmp_path: Path) -> None:
        empty_py = tmp_path / "empty.py"
        empty_py.write_text("", encoding="utf-8")
        result: dict = get_file_structure(str(empty_py))
        assert result["imports"] == []
        assert result["classes"] == []
        assert result["functions"] == []
        assert result["error"] is None

    def test_syntax_error_returns_error(self, tmp_path: Path) -> None:
        bad_py = tmp_path / "bad.py"
        bad_py.write_text("def broken(\n", encoding="utf-8")
        result: dict = get_file_structure(str(bad_py))
        assert result["error"] is not None
        assert isinstance(result["error"], str)


class TestFindReferences:
    def test_finds_symbol_across_files(self, sample_project: Path) -> None:
        result: dict = find_references("greet", str(sample_project))
        assert result["symbol"] == "greet"
        assert result["count"] >= 1
        files_in_refs = [ref["file"] for ref in result["references"]]
        assert str(sample_project / "module_a.py") in files_in_refs
        assert str(sample_project / "consumer.py") in files_in_refs

    def test_no_matches_returns_empty(self, sample_project: Path) -> None:
        result: dict = find_references("nonexistent_symbol_xyz", str(sample_project))
        assert result["references"] == []
        assert result["count"] == 0

    def test_reference_has_line_and_content(self, sample_project: Path) -> None:
        result: dict = find_references("MyClass", str(sample_project))
        for ref in result["references"]:
            assert "file" in ref
            assert "line" in ref
            assert "content" in ref
            assert isinstance(ref["line"], int)
            assert isinstance(ref["content"], str)

    def test_invalid_project_root_returns_error(self) -> None:
        result: dict = find_references("greet", "/nonexistent/root")
        assert result["error"] is not None


class TestGetImpactAnalysis:
    def test_impact_on_changed_file(self, sample_project: Path) -> None:
        result: dict = get_impact_analysis(
            str(sample_project / "module_a.py"), str(sample_project)
        )
        assert result["changed_file"] == str(sample_project / "module_a.py")
        assert "greet" in result["defines"] or "MyClass" in result["defines"]
        assert result["count"] >= 1
        impacted_files = [item["file"] for item in result["impacted_files"]]
        assert str(sample_project / "consumer.py") in impacted_files

    def test_no_impact(self, tmp_path: Path) -> None:
        isolated_py = tmp_path / "isolated.py"
        isolated_py.write_text(
            "def solo() -> None:\n    pass\n", encoding="utf-8"
        )
        result: dict = get_impact_analysis(str(isolated_py), str(tmp_path))
        assert result["impacted_files"] == []
        assert result["count"] == 0

    def test_nonexistent_file_returns_error(self, tmp_path: Path) -> None:
        result: dict = get_impact_analysis(
            str(tmp_path / "nope.py"), str(tmp_path)
        )
        assert result["error"] is not None

    def test_syntax_error_file_returns_error(self, tmp_path: Path) -> None:
        bad_py = tmp_path / "bad.py"
        bad_py.write_text("def broken(\n", encoding="utf-8")
        result: dict = get_impact_analysis(str(bad_py), str(tmp_path))
        assert result["error"] is not None
