"""
Task History API Endpoints.
Provides REST routes for listing, inspecting, deleting, and downloading persistent tasks.
"""

import json
from typing import Any, Dict, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.models.database import get_db
from app.schemas.task_history_schema import (
    TaskDeleteResponse,
    TaskDetailResponse,
    TaskListResponse,
    TaskSummaryResponse,
)
from app.services.task_service import task_service

router = APIRouter(prefix="/tasks", tags=["Task History"])


@router.get(
    "",
    response_model=TaskListResponse,
    status_code=status.HTTP_200_OK,
    summary="List Task History",
    description="Returns recent execution tasks with pagination support, ordered newest first.",
)
def list_tasks(
    limit: int = Query(50, ge=1, le=100, description="Max tasks to return"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    db: Session = Depends(get_db),
) -> TaskListResponse:
    """
    Retrieves a paginated list of recent task execution records.
    """
    tasks, total_count = task_service.get_recent_tasks(db, limit=limit, offset=offset)
    task_summaries = [
        TaskSummaryResponse(
            id=t.id,
            user_message=t.user_message,
            intent=t.intent,
            target_url=t.target_url,
            status=t.status,
            exit_code=t.exit_code,
            execution_duration=t.execution_duration,
            created_at=t.created_at.isoformat() if t.created_at else None,
            completed_at=t.completed_at.isoformat() if t.completed_at else None,
        )
        for t in tasks
    ]
    return TaskListResponse(
        tasks=task_summaries,
        total=total_count,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/{task_id}",
    response_model=TaskDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Task Details",
    description="Retrieves comprehensive details for a specific task ID including stdout and stderr.",
)
def get_task(
    task_id: str,
    db: Session = Depends(get_db),
) -> TaskDetailResponse:
    """
    Fetches the full task record, parsing result_json if present.
    """
    task = task_service.get_task_by_id(db, task_id)
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task with ID '{task_id}' not found.",
        )

    parsed_res: Optional[Dict[str, Any]] = None
    if task.result_json:
        try:
            parsed_res = json.loads(task.result_json)
        except Exception:
            parsed_res = None

    return TaskDetailResponse(
        id=task.id,
        user_message=task.user_message,
        intent=task.intent,
        target_url=task.target_url,
        status=task.status,
        exit_code=task.exit_code,
        execution_duration=task.execution_duration,
        created_at=task.created_at.isoformat() if task.created_at else None,
        completed_at=task.completed_at.isoformat() if task.completed_at else None,
        stdout=task.stdout or "",
        stderr=task.stderr or "",
        result_json=task.result_json,
        error_message=task.error_message,
        parsed_result=parsed_res,
    )


@router.delete(
    "/{task_id}",
    response_model=TaskDeleteResponse,
    status_code=status.HTTP_200_OK,
    summary="Delete Task",
    description="Deletes a specified task record from persistent storage.",
)
def delete_task(
    task_id: str,
    db: Session = Depends(get_db),
) -> TaskDeleteResponse:
    """
    Permanently deletes a task record.
    """
    deleted = task_service.delete_task(db, task_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task with ID '{task_id}' not found or already deleted.",
        )
    return TaskDeleteResponse(
        success=True,
        message=f"Task '{task_id}' deleted successfully.",
        task_id=task_id,
    )


@router.get(
    "/{task_id}/result",
    status_code=status.HTTP_200_OK,
    summary="Download Validated Crawl Result",
    description="Returns the raw validated JSON result for direct inspection or download.",
)
def get_task_result(
    task_id: str,
    db: Session = Depends(get_db),
) -> Response:
    """
    Returns the parsed crawl result JSON payload with content-disposition header for file download.
    """
    task = task_service.get_task_by_id(db, task_id)
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task with ID '{task_id}' not found.",
        )

    if not task.result_json:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task '{task_id}' has no validated result JSON (status: {task.status}).",
        )

    try:
        data = json.loads(task.result_json)
        return JSONResponse(
            content=data,
            headers={
                "Content-Disposition": f'attachment; filename="cli-agent-task-{task_id}.json"'
            },
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to parse stored result JSON: {str(exc)}",
        )
