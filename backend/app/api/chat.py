"""
Conversational Chat API Router.
Handles natural language intent processing via Groq AI, executes approved CLI commands,
records persistent task telemetry in SQLite, and returns full execution metrics.
"""

import json
import logging
from typing import Optional
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.models.database import get_db
from app.schemas.chat_schema import ChatRequest, ChatResponse, ExecutionTelemetry, IntentPayload
from app.services.cli_executor import cli_executor
from app.services.groq_service import groq_service
from app.services.task_service import task_service

logger = logging.getLogger("cli_agent.chat_api")

router = APIRouter(tags=["Conversational Agent"])


@router.post(
    "/chat",
    response_model=ChatResponse,
    status_code=status.HTTP_200_OK,
    summary="Process Natural Language Instruction",
    description="Understands user intent with Groq AI, executes sandboxed Typer CLI commands, and stores persistent task records in SQLite.",
)
async def process_chat_message(
    payload: ChatRequest,
    db: Session = Depends(get_db),
) -> ChatResponse:
    """
    Main conversational agent workflow:
    1. Create task record in SQLite database.
    2. Parse natural language intent via Groq AI.
    3. If invalid/unsupported, update task status to 'rejected' and return.
    4. If valid, dispatch to sandboxed CLI subprocess (shell=False).
    5. Capture stdout, stderr, exit code, and execution duration.
    6. Validate JSON output from the CLI engine.
    7. Update task record in SQLite with full execution telemetry.
    8. Return response containing task_id to the client.
    """
    # 1. Create persistent task record in SQLite
    task = None
    try:
        task = task_service.create_task(db, user_message=payload.message)
    except Exception as exc:
        logger.error("Failed to persist initial task record: %s", str(exc))

    task_id: Optional[str] = task.id if task else None

    try:
        # 2. Groq Intent Classification
        intent_result = await groq_service.understand_intent(payload.message)

        # 3. Handle Unsupported or Invalid Intent
        if not intent_result.is_supported or not intent_result.crawl_intent:
            err_msg = (
                intent_result.unsupported_intent.message
                if intent_result.unsupported_intent
                else (intent_result.error_message or "The requested operation is not supported.")
            )

            if task:
                task_service.update_task_execution(
                    db=db,
                    task_id=task.id,
                    status="rejected",
                    exit_code=-1,
                    stdout="",
                    stderr=intent_result.error_message or "Request rejected by security and intent validator.",
                    error_message=err_msg,
                    execution_duration=0.0,
                    intent="unsupported",
                )

            return ChatResponse(
                success=False,
                task_id=task_id,
                message=err_msg,
                intent=IntentPayload(intent="unsupported"),
                execution=ExecutionTelemetry(
                    status="rejected",
                    exit_code=-1,
                    duration_seconds=0.0,
                    stdout="",
                    stderr=intent_result.error_message or "Request rejected by security and intent validator.",
                ),
                result=None,
            )

        crawl_intent = intent_result.crawl_intent

        # 4. Execute Controlled Subprocess
        exec_result = await cli_executor.execute_crawl(crawl_intent)

        # 5. Persist Full Telemetry to SQLite
        result_json_str = (
            exec_result.parsed_crawl_result.model_dump_json()
            if exec_result.parsed_crawl_result
            else None
        )

        if task:
            task_service.update_task_execution(
                db=db,
                task_id=task.id,
                status=exec_result.execution.status,
                exit_code=exec_result.execution.exit_code,
                stdout=exec_result.execution.stdout,
                stderr=exec_result.execution.stderr,
                result_json=result_json_str,
                error_message=exec_result.message if not exec_result.success else None,
                execution_duration=exec_result.execution.duration_seconds,
                intent=crawl_intent.intent,
                target_url=str(crawl_intent.url),
            )

        # 6. Return Structured Response
        return ChatResponse(
            success=exec_result.success,
            task_id=task_id,
            message=exec_result.message,
            intent=IntentPayload(
                intent=crawl_intent.intent,
                url=str(crawl_intent.url),
                max_pages=crawl_intent.max_pages,
                max_depth=crawl_intent.max_depth,
            ),
            execution=ExecutionTelemetry(
                status=exec_result.execution.status,
                exit_code=exec_result.execution.exit_code,
                duration_seconds=exec_result.execution.duration_seconds,
                stdout=exec_result.execution.stdout,
                stderr=exec_result.execution.stderr,
            ),
            result=exec_result.parsed_crawl_result.model_dump() if exec_result.parsed_crawl_result else None,
        )

    except Exception as exc:
        logger.error("Unhandled exception in process_chat_message: %s", str(exc), exc_info=True)
        if task:
            task_service.update_task_execution(
                db=db,
                task_id=task.id,
                status="failed",
                exit_code=-1,
                stdout="",
                stderr=str(exc),
                error_message=str(exc),
                execution_duration=0.0,
            )
        raise
