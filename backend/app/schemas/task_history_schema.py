"""
Pydantic schemas for Task History API endpoints.
Provides serializable representations for task list, detail, and deletion responses.
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class TaskSummaryResponse(BaseModel):
    """Summarized task record for sidebar history lists."""
    id: str = Field(..., description="Unique task identifier")
    user_message: str = Field(..., description="Original user prompt")
    intent: Optional[str] = Field(default=None, description="Classified intent")
    target_url: Optional[str] = Field(default=None, description="Target website URL")
    status: str = Field(..., description="Execution status: completed, failed, timeout, rejected, invalid_output")
    exit_code: Optional[int] = Field(default=None, description="CLI process exit code")
    execution_duration: float = Field(default=0.0, description="Execution duration in seconds")
    created_at: Optional[str] = Field(default=None, description="ISO timestamp when created")
    completed_at: Optional[str] = Field(default=None, description="ISO timestamp when completed")

    model_config = ConfigDict(from_attributes=True)


class TaskDetailResponse(TaskSummaryResponse):
    """Complete task record including stdout, stderr, and result payload."""
    stdout: Optional[str] = Field(default="", description="Captured standard output")
    stderr: Optional[str] = Field(default="", description="Captured diagnostic error output")
    result_json: Optional[str] = Field(default=None, description="Raw validated JSON result string")
    error_message: Optional[str] = Field(default=None, description="Error diagnostics")
    parsed_result: Optional[Dict[str, Any]] = Field(default=None, description="Parsed JSON object")

    model_config = ConfigDict(from_attributes=True)


class TaskListResponse(BaseModel):
    """Paginated collection of task history records."""
    tasks: List[TaskSummaryResponse] = Field(default_factory=list, description="Task items")
    total: int = Field(default=0, description="Total number of tasks stored")
    limit: int = Field(default=50, description="Pagination page limit")
    offset: int = Field(default=0, description="Pagination offset")


class TaskDeleteResponse(BaseModel):
    """Response returned upon deleting a task record."""
    success: bool
    message: str
    task_id: str
