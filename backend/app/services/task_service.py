"""
Task service module.
Provides safe database operations for managing task records, execution telemetry,
and validated crawl results.
"""

from datetime import datetime, timezone
import logging
from typing import List, Optional, Tuple
from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from app.models.task import TaskModel

logger = logging.getLogger("cli_agent.task_service")

# Limit saved stdout/stderr text to 500 KB to avoid SQLite bloat
MAX_DB_TEXT_BYTES = 500 * 1024


class TaskService:
    """
    Service layer providing CRUD operations for TaskModel records.
    """

    @classmethod
    def create_task(
        cls,
        db: Session,
        user_message: str,
        intent: Optional[str] = None,
        target_url: Optional[str] = None,
        status: str = "running",
    ) -> TaskModel:
        """
        Creates and persists a new TaskModel record upon receiving a user prompt.
        """
        task = TaskModel(
            user_message=user_message.strip(),
            intent=intent,
            target_url=target_url,
            status=status,
            created_at=datetime.now(timezone.utc),
        )
        try:
            db.add(task)
            db.commit()
            db.refresh(task)
            logger.info("Created task record with ID: %s", task.id)
            return task
        except Exception as exc:
            db.rollback()
            logger.error("Failed to create task in database: %s", str(exc))
            raise

    @classmethod
    def update_task_execution(
        cls,
        db: Session,
        task_id: str,
        status: str,
        exit_code: Optional[int] = None,
        stdout: Optional[str] = None,
        stderr: Optional[str] = None,
        result_json: Optional[str] = None,
        error_message: Optional[str] = None,
        execution_duration: float = 0.0,
        intent: Optional[str] = None,
        target_url: Optional[str] = None,
    ) -> Optional[TaskModel]:
        """
        Updates an existing task record with CLI execution output and telemetry.
        """
        task = cls.get_task_by_id(db, task_id)
        if not task:
            logger.warning("Attempted to update non-existent task: %s", task_id)
            return None

        # Truncate large stdout / stderr payloads before saving to SQLite
        if stdout and len(stdout.encode("utf-8")) > MAX_DB_TEXT_BYTES:
            stdout = stdout[:MAX_DB_TEXT_BYTES] + "\n...[truncated for storage]"

        if stderr and len(stderr.encode("utf-8")) > MAX_DB_TEXT_BYTES:
            stderr = stderr[:MAX_DB_TEXT_BYTES] + "\n...[truncated for storage]"

        task.status = status
        task.exit_code = exit_code
        task.stdout = stdout
        task.stderr = stderr
        task.result_json = result_json
        task.error_message = error_message
        task.execution_duration = execution_duration
        task.completed_at = datetime.now(timezone.utc)

        if intent:
            task.intent = intent
        if target_url:
            task.target_url = target_url

        try:
            db.commit()
            db.refresh(task)
            logger.info("Updated task %s: status=%s, exit_code=%s, duration=%ss",
                        task_id, status, exit_code, execution_duration)
            return task
        except Exception as exc:
            db.rollback()
            logger.error("Failed to update task %s in database: %s", task_id, str(exc))
            raise

    @classmethod
    def get_task_by_id(cls, db: Session, task_id: str) -> Optional[TaskModel]:
        """
        Retrieves a task by its unique ID.
        """
        if not task_id or not isinstance(task_id, str):
            return None
        try:
            return db.query(TaskModel).filter(TaskModel.id == task_id.strip()).first()
        except Exception as exc:
            logger.error("Database query error in get_task_by_id (%s): %s", task_id, str(exc))
            return None

    @classmethod
    def get_recent_tasks(
        cls,
        db: Session,
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[List[TaskModel], int]:
        """
        Returns a paginated list of recent tasks, newest first, alongside total count.
        """
        safe_limit = max(1, min(limit, 100))
        safe_offset = max(0, offset)

        try:
            total_count = db.query(func.count(TaskModel.id)).scalar() or 0
            tasks = (
                db.query(TaskModel)
                .order_by(desc(TaskModel.created_at))
                .offset(safe_offset)
                .limit(safe_limit)
                .all()
            )
            return tasks, total_count
        except Exception as exc:
            logger.error("Database error in get_recent_tasks: %s", str(exc))
            return [], 0

    @classmethod
    def delete_task(cls, db: Session, task_id: str) -> bool:
        """
        Deletes a task record by ID. Returns True if deleted, False if not found.
        """
        task = cls.get_task_by_id(db, task_id)
        if not task:
            return False

        try:
            db.delete(task)
            db.commit()
            logger.info("Deleted task record: %s", task_id)
            return True
        except Exception as exc:
            db.rollback()
            logger.error("Database error in delete_task (%s): %s", task_id, str(exc))
            raise


task_service = TaskService()
