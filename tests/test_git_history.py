from __future__ import annotations

from subprocess import CompletedProcess
from typing import Any
from unittest.mock import patch

import pytest

from mcp_servers.code_intelligence_server import tool_get_file_history


class TestGetFileHistory:
    def test_returns_list_of_dicts_on_success(self) -> None:
        mock_stdout = (
            "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0|2026-06-03 10:00:00 +0900|feat: add incremental index\n"
            "b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1|2026-06-02 15:30:00 +0900|fix: resolve parse error\n"
        )
        mock_result = CompletedProcess(
            args=["git", "log"],
            returncode=0,
            stdout=mock_stdout,
            stderr="",
        )
        with patch("mcp_servers.code_intelligence_server.subprocess.run", return_value=mock_result):
            result = tool_get_file_history("mcp_servers/code_intelligence_server.py")

        assert isinstance(result, list)
        assert len(result) == 2
        assert result[0] == {
            "hash": "a1b2c3d4",
            "date": "2026-06-03 10:00:00 +0900",
            "message": "feat: add incremental index",
        }
        assert result[1] == {
            "hash": "b2c3d4e5",
            "date": "2026-06-02 15:30:00 +0900",
            "message": "fix: resolve parse error",
        }

    def test_returns_error_when_not_git_repo(self) -> None:
        mock_result = CompletedProcess(
            args=["git", "log"],
            returncode=128,
            stdout="",
            stderr="fatal: not a git repository",
        )
        with patch("mcp_servers.code_intelligence_server.subprocess.run", return_value=mock_result):
            result = tool_get_file_history("/nonexistent/path/file.py")

        assert result == [{"error": "Not a git repository or file not found."}]

    def test_returns_empty_list_for_no_history(self) -> None:
        mock_result = CompletedProcess(
            args=["git", "log"],
            returncode=0,
            stdout="",
            stderr="",
        )
        with patch("mcp_servers.code_intelligence_server.subprocess.run", return_value=mock_result):
            result = tool_get_file_history("new_untracked_file.py")

        assert result == []

    def test_max_commits_passed_to_git_log(self) -> None:
        mock_result = CompletedProcess(
            args=["git", "log"],
            returncode=0,
            stdout="a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0|2026-06-03 10:00:00 +0900|msg\n",
            stderr="",
        )
        with patch("mcp_servers.code_intelligence_server.subprocess.run", return_value=mock_result) as mock_run:
            tool_get_file_history("some_file.py", max_commits=5)
            call_args = mock_run.call_args
            cmd = call_args[0][0] if call_args[0] else call_args.kwargs.get("args", [])
            assert "--max-count=5" in cmd

    def test_hash_truncated_to_8_chars(self) -> None:
        long_hash = "abcdef1234567890abcdef1234567890abcdef12"
        mock_stdout = f"{long_hash}|2026-06-03 10:00:00 +0900|test message\n"
        mock_result = CompletedProcess(
            args=["git", "log"],
            returncode=0,
            stdout=mock_stdout,
            stderr="",
        )
        with patch("mcp_servers.code_intelligence_server.subprocess.run", return_value=mock_result):
            result = tool_get_file_history("file.py")

        assert len(result) == 1
        assert len(result[0]["hash"]) == 8
        assert result[0]["hash"] == "abcdef12"

    def test_default_max_commits_is_10(self) -> None:
        mock_result = CompletedProcess(
            args=["git", "log"],
            returncode=0,
            stdout="",
            stderr="",
        )
        with patch("mcp_servers.code_intelligence_server.subprocess.run", return_value=mock_result) as mock_run:
            tool_get_file_history("file.py")
            call_args = mock_run.call_args
            cmd = call_args[0][0] if call_args[0] else call_args.kwargs.get("args", [])
            assert "--max-count=10" in cmd
