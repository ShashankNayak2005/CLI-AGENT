"""
Tests for CLIExecutor controlled subprocess management.
Covers:
7. CLI subprocess receives the correct arguments.
8. subprocess uses shell=False.
9. CLI timeout is handled.
10. Non-zero CLI exit code is handled.
11. Invalid CLI JSON output is rejected.
"""

import subprocess
from unittest.mock import MagicMock, patch
import pytest

from app.schemas.intent_schema import CrawlIntent
from app.services.cli_executor import CLIExecutor


@pytest.fixture
def valid_intent():
    return CrawlIntent(
        intent="crawl_website",
        url="https://example.com",
        max_pages=3,
        max_depth=1,
        output="json",
    )


@pytest.mark.anyio
async def test_subprocess_receives_correct_args(valid_intent):
    with patch("subprocess.run") as mock_run:
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        valid_json = b'{"success": true, "status": "completed", "target_url": "https://example.com/", "pages_crawled": 1, "pages_failed": 0, "execution_time_seconds": 0.5, "website_summary": {"title": "Test", "description": "desc", "headings": [], "main_content": []}, "pages": [], "errors": []}'
        mock_proc.stdout = valid_json
        mock_proc.stderr = b"[INFO] Log line"
        mock_run.return_value = mock_proc

        result = await CLIExecutor.execute_crawl(valid_intent)

        assert result.success is True
        assert mock_run.called
        args_passed = mock_run.call_args[0][0]
        kwargs_passed = mock_run.call_args[1]

        # Verify arguments
        assert "-m" in args_passed
        assert "app.cli.main" in args_passed
        assert "crawl" in args_passed
        assert "--url" in args_passed
        assert "https://example.com/" in args_passed
        assert "--max-pages" in args_passed
        assert "3" in args_passed

        # Verify shell=False is strictly enforced
        assert kwargs_passed.get("shell") is False


@pytest.mark.anyio
async def test_subprocess_timeout_handled(valid_intent):
    with patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd=["python"], timeout=10.0)):
        result = await CLIExecutor.execute_crawl(valid_intent, timeout=0.01)

        assert result.success is False
        assert result.execution.status == "timeout"
        assert result.execution.exit_code == -1
        assert "timed out" in result.message.lower()


@pytest.mark.anyio
async def test_nonzero_exit_code_handled(valid_intent):
    with patch("subprocess.run") as mock_run:
        mock_proc = MagicMock()
        mock_proc.returncode = 3
        mock_proc.stdout = b""
        mock_proc.stderr = b"[ERROR] No pages were successfully crawled"
        mock_run.return_value = mock_proc

        result = await CLIExecutor.execute_crawl(valid_intent)

        assert result.success is False
        assert result.execution.status == "failed"
        assert result.execution.exit_code == 3
        assert "failed with exit code 3" in result.message


@pytest.mark.anyio
async def test_invalid_cli_json_output_rejected(valid_intent):
    with patch("subprocess.run") as mock_run:
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stdout = b"Random text output not JSON"
        mock_proc.stderr = b""
        mock_run.return_value = mock_proc

        result = await CLIExecutor.execute_crawl(valid_intent)

        assert result.success is False
        assert result.execution.status == "invalid_output"
        assert "does not match the required JSON schema" in result.message
