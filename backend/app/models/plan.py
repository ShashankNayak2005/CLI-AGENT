"""
SQLAlchemy models for multi-step AI Agent Plans and Steps.
Extends persistent SQLite storage while preserving existing task history.
"""

from datetime import datetime, timezone
import json
from typing import Any, Dict, List, Optional
import uuid

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.models.database import Base


def generate_plan_id() -> str:
    """Generates a unique prefixed plan identifier."""
    return f"plan_{uuid.uuid4().hex[:12]}"


class PlanModel(Base):
    """
    Persistent record representing an approved or pending multi-step AI execution plan.
    """
    __tablename__ = "plans"

    id = Column(String(36), primary_key=True, default=generate_plan_id, index=True)
    goal = Column(Text, nullable=False)
    user_request = Column(Text, nullable=False)
    status = Column(
        String(50),
        nullable=False,
        default="pending",
        index=True,
        # States: 'pending', 'approved', 'running', 'completed', 'failed', 'cancelled'
    )
    plan_json = Column(Text, nullable=False)
    final_result_json = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    approved_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    error_message = Column(Text, nullable=True)
    total_duration = Column(Float, default=0.0)

    # Relationship to ordered steps
    steps = relationship(
        "PlanStepModel",
        back_populates="plan",
        cascade="all, delete-orphan",
        order_by="PlanStepModel.step_id",
    )

    def to_dict(self) -> Dict[str, Any]:
        """Serializes the plan model with all steps."""
        return {
            "plan_id": self.id,
            "goal": self.goal,
            "user_request": self.user_request,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "approved_at": self.approved_at.isoformat() if self.approved_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "total_duration": self.total_duration,
            "error_message": self.error_message,
            "steps": [s.to_dict() for s in self.steps],
            "final_result": json.loads(self.final_result_json) if self.final_result_json else None,
        }


class PlanStepModel(Base):
    """
    Persistent record representing a step within a multi-step plan.
    """
    __tablename__ = "plan_steps"

    id = Column(Integer, primary_key=True, autoincrement=True)
    plan_id = Column(String(36), ForeignKey("plans.id"), index=True, nullable=False)
    step_id = Column(Integer, nullable=False)
    operation = Column(String(50), nullable=False)
    description = Column(Text, nullable=True)
    depends_on_json = Column(Text, default="[]")
    parameters_json = Column(Text, default="{}")
    status = Column(
        String(50),
        default="pending",
        nullable=False,
        # States: 'pending', 'running', 'completed', 'failed', 'skipped'
    )
    duration_seconds = Column(Float, default=0.0)
    output_json = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    plan = relationship("PlanModel", back_populates="steps")

    def to_dict(self) -> Dict[str, Any]:
        """Serializes the step model."""
        return {
            "step_id": self.step_id,
            "operation": self.operation,
            "description": self.description or "",
            "depends_on": json.loads(self.depends_on_json) if self.depends_on_json else [],
            "parameters": json.loads(self.parameters_json) if self.parameters_json else {},
            "status": self.status,
            "duration_seconds": self.duration_seconds,
            "output": json.loads(self.output_json) if self.output_json else None,
            "error": self.error_message,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }

