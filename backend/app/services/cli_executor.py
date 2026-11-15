"""
Controlled CLI Subprocess Execution Service.
Safely executes approved CLI commands using sys.executable and asyncio subprocesses.
Strictly enforces shell=False, individual argument passing, timeouts, output size limits,
and Pydantic validation of CLI JSON outputs.
"""

import asyncio
from datetime import datetime, timezone
import logging
from pathlib import Path
import subprocess
import sys
import time
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from app.config import BASE_DIR
from app.schemas.crawl_schema import CrawlResult
from app.schemas.intent_schema import CrawlIntent

logger = logging.getLogger("cli_agent.executor")

# Maximum permitted process output capture size (5 MB)
MAX_CAPTURE_BYTES = 5 * 1024 * 1024
DEFAULT_PROCESS_TIMEOUT = 60.0  # seconds


class ProcessExecutionDetails(BaseModel):
    """
    Detailed telemetry captured from the CLI process execution.
    """
    status: str = Field(..., description="Process status: completed, failed, timeout, rejected, invalid_output")
    exit_code: Optional[int] = Field(default=None, description="Process termination return code")
    duration_seconds: float = Field(default=0.0, description="Process execution duration in seconds")
    command_executed: List[str] = Field(default_factory=list, description="Sanitized command tokens executed")
    stdout: str = Field(default="", description="Captured standard output")
    stderr: str = Field(default="", description="Captured standard error / diagnostic logs")
    error_message: Optional[str] = Field(default=None, description="Process failure or timeout reason")


class CLIExecutorResult(BaseModel):
    """
    Aggregated result container combining process telemetry and parsed schema data.
    """
    success: bool
    execution: ProcessExecutionDetails
    parsed_crawl_result: Optional[CrawlResult] = None
    message: str = ""


class CLIExecutor:
    """
    Orchestrates sandboxed CLI subprocess executions.
    """

    @classmethod
    async def execute_crawl(
        cls,
        intent: CrawlIntent,
        timeout: float = DEFAULT_PROCESS_TIMEOUT,
    ) -> CLIExecutorResult:
        """
        Executes the 'crawl' command using the local Typer CLI entry point.
        Command equivalent:
            python -m app.cli.main crawl --url <url> --max-pages <p> --max-depth <d> --output json
        """
        # 1. Construct explicit, tokenized argument list (NEVER shell=True, NEVER string concatenation)
        cmd_args: List[str] = [
            sys.executable,
            "-m",
            "app.cli.main",
            "crawl",
            "--url",
            str(intent.url),
            "--max-pages",
            str(intent.max_pages),
            "--max-depth",
            str(intent.max_depth),
            "--output",
            "json",
        ]

        # Sanitize command for public telemetry (replace local python executable path with 'python')
        telemetry_cmd = ["python"] + cmd_args[1:]

        start_time = time.perf_counter()
        sys.stderr.write(f"[EXECUTOR] Launching subprocess: {' '.join(telemetry_cmd)}\n")
        sys.stderr.flush()

        def _run_subprocess() -> subprocess.CompletedProcess:
            return subprocess.run(
                cmd_args,
                cwd=str(BASE_DIR),
                capture_output=True,
                timeout=timeout,
                shell=False,
            )

        try:
            # Execute subprocess with shell=False in thread pool to prevent event-loop blocking
            proc_result = await asyncio.to_thread(_run_subprocess)
            stdout_bytes = proc_result.stdout
            stderr_bytes = proc_result.stderr
            exit_code = proc_result.returncode

        except subprocess.TimeoutExpired as texc:
            duration = round(time.perf_counter() - start_time, 2)
            sys.stderr.write(f"[EXECUTOR] Process timed out after {timeout} seconds\n")
            sys.stderr.flush()
            return CLIExecutorResult(
                success=False,
                message=f"CLI execution timed out after {timeout} seconds.",
                execution=ProcessExecutionDetails(
                    status="timeout",
                    exit_code=-1,
                    duration_seconds=duration,
                    command_executed=telemetry_cmd,
                    stdout=(texc.stdout or b"")[:MAX_CAPTURE_BYTES].decode("utf-8", errors="replace"),
                    stderr=f"Process exceeded timeout limit of {timeout}s and was terminated.",
                    error_message="Process timed out.",
                ),
            )
        except Exception as exc:
            duration = round(time.perf_counter() - start_time, 2)
            sys.stderr.write(f"[EXECUTOR] Subprocess spawn failed: {type(exc).__name__}: {repr(exc)}\n")
            sys.stderr.flush()

            return CLIExecutorResult(
                success=False,
                message=f"Failed to execute CLI process: {type(exc).__name__}: {str(exc)}",
                execution=ProcessExecutionDetails(
                    status="failed",
                    exit_code=-1,
                    duration_seconds=duration,
                    command_executed=telemetry_cmd,
                    stdout="",
                    stderr=f"{type(exc).__name__}: {str(exc)}",
                    error_message=f"{type(exc).__name__}: {str(exc)}",
                ),
            )

        duration = round(time.perf_counter() - start_time, 2)

        # 4. Limit captured output size to prevent memory exhaustion
        stdout_text = stdout_bytes[:MAX_CAPTURE_BYTES].decode("utf-8", errors="replace").strip()
        stderr_text = stderr_bytes[:MAX_CAPTURE_BYTES].decode("utf-8", errors="replace").strip()

        sys.stderr.write(f"[EXECUTOR] Process finished in {duration}s with exit code {exit_code}\n")
        sys.stderr.flush()

        # 5. Handle Non-Zero Exit Code
        if exit_code != 0:
            return CLIExecutorResult(
                success=False,
                message=f"CLI process failed with exit code {exit_code}.",
                execution=ProcessExecutionDetails(
                    status="failed",
                    exit_code=exit_code,
                    duration_seconds=duration,
                    command_executed=telemetry_cmd,
                    stdout=stdout_text,
                    stderr=stderr_text,
                    error_message=f"CLI exited with code {exit_code}.",
                ),
            )

        # 6. Parse and Validate Expected JSON Output
        if not stdout_text:
            return CLIExecutorResult(
                success=False,
                message="CLI process exited successfully but produced empty output.",
                execution=ProcessExecutionDetails(
                    status="invalid_output",
                    exit_code=exit_code,
                    duration_seconds=duration,
                    command_executed=telemetry_cmd,
                    stdout="",
                    stderr=stderr_text,
                    error_message="Empty stdout received from CLI process.",
                ),
            )

        try:
            parsed_result = CrawlResult.model_validate_json(stdout_text)
        except Exception as exc:
            sys.stderr.write(f"[EXECUTOR] Failed to parse CLI output as CrawlResult: {str(exc)}\n")
            sys.stderr.flush()
            return CLIExecutorResult(
                success=False,
                message="CLI process produced output that does not match the required JSON schema.",
                execution=ProcessExecutionDetails(
                    status="invalid_output",
                    exit_code=exit_code,
                    duration_seconds=duration,
                    command_executed=telemetry_cmd,
                    stdout=stdout_text,
                    stderr=stderr_text,
                    error_message=f"JSON validation error: {str(exc)}",
                ),
            )

        # 7. Successful Execution and Validation
        pages_count = parsed_result.pages_crawled
        return CLIExecutorResult(
            success=True,
            message=f"Website crawl completed successfully. Extracted {pages_count} page(s).",
            execution=ProcessExecutionDetails(
                status="completed",
                exit_code=0,
                duration_seconds=duration,
                command_executed=telemetry_cmd,
                stdout=stdout_text,
                stderr=stderr_text,
            ),
            parsed_crawl_result=parsed_result,
        )


# Global executor instance
cli_executor = CLIExecutor()
