import json
import shutil
import subprocess
from collections import defaultdict
from typing import Any

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("lsp-server")


def _run_pyright(args: list[str]) -> dict[str, Any]:
    result = subprocess.run(
        ["pyright", "--outputjson"] + args,
        capture_output=True,
        text=True,
    )
    try:
        return json.loads(result.stdout)
    except (json.JSONDecodeError, TypeError):
        return {"generalDiagnostics": [], "_raw_error": result.stderr or result.stdout}


def _parse_diagnostics(
    pyright_data: dict[str, Any], target_file: str | None = None
) -> tuple[list[dict[str, Any]], int, int]:
    details: list[dict[str, Any]] = []
    error_count = 0
    warning_count = 0

    for diag in pyright_data.get("generalDiagnostics", []):
        file = diag.get("file", "")
        if target_file and file != target_file:
            continue
        severity = diag.get("severity", "information")
        line = diag.get("range", {}).get("start", {}).get("line", 0)
        message = diag.get("message", "")

        details.append({"line": line, "message": message, "severity": severity})

        if severity == "error":
            error_count += 1
        elif severity == "warning":
            warning_count += 1

    return details, error_count, warning_count


@mcp.tool()
def check_types(file_path: str) -> dict:
    if not shutil.which("pyright"):
        return {
            "file": file_path,
            "errors": 0,
            "warnings": 0,
            "passed": False,
            "details": [],
            "error": "pyright is not installed. Run: npm install -g pyright",
        }

    pyright_data = _run_pyright([file_path])

    if "_raw_error" in pyright_data:
        return {
            "file": file_path,
            "errors": 0,
            "warnings": 0,
            "passed": False,
            "details": [],
            "error": pyright_data["_raw_error"] or "Failed to parse pyright output",
        }

    details, error_count, warning_count = _parse_diagnostics(pyright_data, file_path)

    return {
        "file": file_path,
        "errors": error_count,
        "warnings": warning_count,
        "passed": error_count == 0,
        "details": details,
    }


@mcp.tool()
def get_diagnostics(project_root: str) -> dict:
    if not shutil.which("pyright"):
        return {
            "project_root": project_root,
            "total_errors": 0,
            "total_warnings": 0,
            "files_with_errors": [],
            "passed": False,
            "error": "pyright is not installed. Run: npm install -g pyright",
        }

    pyright_data = _run_pyright([project_root])

    if "_raw_error" in pyright_data:
        return {
            "project_root": project_root,
            "total_errors": 0,
            "total_warnings": 0,
            "files_with_errors": [],
            "passed": False,
            "error": pyright_data["_raw_error"] or "Failed to parse pyright output",
        }

    details, total_errors, total_warnings = _parse_diagnostics(pyright_data)

    file_error_map: dict[str, int] = defaultdict(int)
    for diag in pyright_data.get("generalDiagnostics", []):
        severity = diag.get("severity", "information")
        if severity == "error":
            file_error_map[diag.get("file", "")] += 1

    files_with_errors = [
        {"file": f, "errors": count} for f, count in sorted(file_error_map.items())
    ]

    return {
        "project_root": project_root,
        "total_errors": total_errors,
        "total_warnings": total_warnings,
        "files_with_errors": files_with_errors,
        "passed": total_errors == 0,
    }


if __name__ == "__main__":
    mcp.run()
