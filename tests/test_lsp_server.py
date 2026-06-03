import json
import subprocess
from unittest.mock import MagicMock, patch

import pytest

from mcp_servers.lsp_server import check_types, get_diagnostics


class TestCheckTypes:
    def test_check_types_with_errors(self) -> None:
        pyright_output = {
            "generalDiagnostics": [
                {
                    "file": "path/to/file.py",
                    "range": {"start": {"line": 10}},
                    "message": "Type error: ...",
                    "severity": "error",
                },
                {
                    "file": "path/to/file.py",
                    "range": {"start": {"line": 20}},
                    "message": "Warning: ...",
                    "severity": "warning",
                },
            ]
        }
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = json.dumps(pyright_output)

        with patch("shutil.which", return_value="/usr/local/bin/pyright"), patch(
            "subprocess.run", return_value=mock_result
        ):
            result = check_types("path/to/file.py")

        assert isinstance(result, dict)
        assert result["file"] == "path/to/file.py"
        assert result["errors"] == 1
        assert result["warnings"] == 1
        assert result["passed"] is False
        assert len(result["details"]) == 2
        assert result["details"][0]["line"] == 10
        assert result["details"][0]["severity"] == "error"
        assert "error" not in result

    def test_check_types_passed(self) -> None:
        pyright_output = {"generalDiagnostics": []}
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps(pyright_output)

        with patch("shutil.which", return_value="/usr/local/bin/pyright"), patch(
            "subprocess.run", return_value=mock_result
        ):
            result = check_types("path/to/file.py")

        assert result["errors"] == 0
        assert result["warnings"] == 0
        assert result["passed"] is True
        assert result["details"] == []

    def test_check_types_pyright_not_installed(self) -> None:
        with patch("shutil.which", return_value=None):
            result = check_types("path/to/file.py")

        assert isinstance(result, dict)
        assert result["file"] == "path/to/file.py"
        assert result["errors"] == 0
        assert result["warnings"] == 0
        assert result["passed"] is False
        assert result["details"] == []
        assert "error" in result
        assert "pyright is not installed" in result["error"]

    def test_check_types_subprocess_error(self) -> None:
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = "not valid json"
        mock_result.stderr = "some error"

        with patch("shutil.which", return_value="/usr/local/bin/pyright"), patch(
            "subprocess.run", return_value=mock_result
        ):
            result = check_types("path/to/file.py")

        assert isinstance(result, dict)
        assert result["file"] == "path/to/file.py"
        assert result["passed"] is False

    def test_check_types_file_not_found(self) -> None:
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = json.dumps({"generalDiagnostics": []})
        mock_result.stderr = "file not found"

        with patch("shutil.which", return_value="/usr/local/bin/pyright"), patch(
            "subprocess.run", return_value=mock_result
        ):
            result = check_types("nonexistent.py")

        assert result["file"] == "nonexistent.py"

    def test_check_types_multiple_errors_same_file(self) -> None:
        pyright_output = {
            "generalDiagnostics": [
                {
                    "file": "path/to/file.py",
                    "range": {"start": {"line": 5}},
                    "message": "Error 1",
                    "severity": "error",
                },
                {
                    "file": "path/to/file.py",
                    "range": {"start": {"line": 15}},
                    "message": "Error 2",
                    "severity": "error",
                },
                {
                    "file": "path/to/file.py",
                    "range": {"start": {"line": 25}},
                    "message": "Error 3",
                    "severity": "error",
                },
            ]
        }
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = json.dumps(pyright_output)

        with patch("shutil.which", return_value="/usr/local/bin/pyright"), patch(
            "subprocess.run", return_value=mock_result
        ):
            result = check_types("path/to/file.py")

        assert result["errors"] == 3
        assert result["warnings"] == 0
        assert result["passed"] is False
        assert len(result["details"]) == 3

    def test_check_types_info_severity(self) -> None:
        pyright_output = {
            "generalDiagnostics": [
                {
                    "file": "path/to/file.py",
                    "range": {"start": {"line": 1}},
                    "message": "Info msg",
                    "severity": "information",
                }
            ]
        }
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps(pyright_output)

        with patch("shutil.which", return_value="/usr/local/bin/pyright"), patch(
            "subprocess.run", return_value=mock_result
        ):
            result = check_types("path/to/file.py")

        assert result["errors"] == 0
        assert result["warnings"] == 0
        assert result["passed"] is True
        assert len(result["details"]) == 1
        assert result["details"][0]["severity"] == "information"


class TestGetDiagnostics:
    def test_get_diagnostics_with_errors(self) -> None:
        pyright_output = {
            "generalDiagnostics": [
                {
                    "file": "src/a.py",
                    "range": {"start": {"line": 10}},
                    "message": "Error in a",
                    "severity": "error",
                },
                {
                    "file": "src/a.py",
                    "range": {"start": {"line": 20}},
                    "message": "Another error in a",
                    "severity": "error",
                },
                {
                    "file": "src/a.py",
                    "range": {"start": {"line": 30}},
                    "message": "Warning in a",
                    "severity": "warning",
                },
                {
                    "file": "src/b.py",
                    "range": {"start": {"line": 5}},
                    "message": "Error in b",
                    "severity": "error",
                },
                {
                    "file": "src/b.py",
                    "range": {"start": {"line": 15}},
                    "message": "Warning in b",
                    "severity": "warning",
                },
            ]
        }
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = json.dumps(pyright_output)

        with patch("shutil.which", return_value="/usr/local/bin/pyright"), patch(
            "subprocess.run", return_value=mock_result
        ):
            result = get_diagnostics("path/to/project")

        assert isinstance(result, dict)
        assert result["project_root"] == "path/to/project"
        assert result["total_errors"] == 3
        assert result["total_warnings"] == 2
        assert result["passed"] is False
        assert len(result["files_with_errors"]) == 2

        file_a = next(f for f in result["files_with_errors"] if f["file"] == "src/a.py")
        assert file_a["errors"] == 2

        file_b = next(f for f in result["files_with_errors"] if f["file"] == "src/b.py")
        assert file_b["errors"] == 1

    def test_get_diagnostics_passed(self) -> None:
        pyright_output = {"generalDiagnostics": []}
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps(pyright_output)

        with patch("shutil.which", return_value="/usr/local/bin/pyright"), patch(
            "subprocess.run", return_value=mock_result
        ):
            result = get_diagnostics("path/to/project")

        assert result["total_errors"] == 0
        assert result["total_warnings"] == 0
        assert result["passed"] is True
        assert result["files_with_errors"] == []

    def test_get_diagnostics_pyright_not_installed(self) -> None:
        with patch("shutil.which", return_value=None):
            result = get_diagnostics("path/to/project")

        assert isinstance(result, dict)
        assert result["project_root"] == "path/to/project"
        assert result["total_errors"] == 0
        assert result["total_warnings"] == 0
        assert result["passed"] is False
        assert "error" in result
        assert "pyright is not installed" in result["error"]

    def test_get_diagnostics_invalid_json(self) -> None:
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = "not valid json"

        with patch("shutil.which", return_value="/usr/local/bin/pyright"), patch(
            "subprocess.run", return_value=mock_result
        ):
            result = get_diagnostics("path/to/project")

        assert isinstance(result, dict)
        assert result["project_root"] == "path/to/project"
        assert result["passed"] is False

    def test_get_diagnostics_only_warnings(self) -> None:
        pyright_output = {
            "generalDiagnostics": [
                {
                    "file": "src/a.py",
                    "range": {"start": {"line": 1}},
                    "message": "Warning",
                    "severity": "warning",
                }
            ]
        }
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps(pyright_output)

        with patch("shutil.which", return_value="/usr/local/bin/pyright"), patch(
            "subprocess.run", return_value=mock_result
        ):
            result = get_diagnostics("path/to/project")

        assert result["total_errors"] == 0
        assert result["total_warnings"] == 1
        assert result["passed"] is True
        assert result["files_with_errors"] == []


class TestMCPServerCreation:
    def test_server_object_exists(self) -> None:
        from mcp_servers.lsp_server import mcp

        assert mcp is not None
        assert hasattr(mcp, "tool")

    def test_check_types_return_type_annotation(self) -> None:
        import inspect

        sig = inspect.signature(check_types)
        assert sig.return_annotation == dict

    def test_get_diagnostics_return_type_annotation(self) -> None:
        import inspect

        sig = inspect.signature(get_diagnostics)
        assert sig.return_annotation == dict
