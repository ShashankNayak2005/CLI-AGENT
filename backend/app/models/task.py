"""
Task database model for persistent task execution history.
Stores all user prompts, parsed intents, CLI process telemetry, and validated crawl JSON.
"""

from datetime import datetime, timezone
import uuid
from typing import Any, Dict, Optional

from sqlalchemy import Column, DateTime, Float, Integer, String, Text
from app.models.database import Base


def generate_task_id() -> str:
    """Generates a unique prefixed task identifier."""
    return f"task_{uuid.uuid4().hex[:12]}"


class TaskModel(Base):
    """
    SQLAlchemy ORM model representing an AI-to-CLI execution task.
    """
    __tablename__ = "tasks"

    id = Column(String(36), primary_key=True, default=generate_task_id, index=True)
    user_message = Column(Text, nullable=False)
    intent = Column(String(100), nullable=True)
    target_url = Column(Text, nullable=True)
    status = Column(
        String(50),
        nullable=False,
        default="running",
        index=True,
        # Valid values: 'running', 'completed', 'failed', 'timeout', 'rejected', 'invalid_output'
    )
    exit_code = Column(Integer, nullable=True)
    stdout = Column(Text, nullable=True)
    stderr = Column(Text, nullable=True)
    result_json = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)
    execution_duration = Column(Float, default=0.0)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    completed_at = Column(DateTime, nullable=True)

    def to_dict(self) -> Dict[str, Any]:
        """Serializes the task model into a clean dictionary."""
        return {
            "id": self.id,
            "user_message": self.user_message,
            "intent": self.intent,
            "target_url": self.target_url,
            "status": self.status,
            "exit_code": self.exit_code,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "result_json": self.result_json,
            "error_message": self.error_message,
            "execution_duration": self.execution_duration,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }
