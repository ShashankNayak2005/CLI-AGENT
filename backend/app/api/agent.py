"""
Multi-Step Agent API Endpoints for CLI Agent AI.
Implements Plan Generation, Human-in-the-Loop Approval, Plan Execution, Cancellation, and Artifact Downloads.
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.config import BASE_DIR
from app.models.database import get_db
from app.models.plan import PlanModel, PlanStepModel
from app.schemas.plan_schema import (
    PlanExecuteRequest,
    PlanExecuteResponse,
    PlanGenerateRequest,
    PlanGenerateResponse,
    TaskPlan,
)
from app.services.agent_executor import AgentExecutor, OUTPUT_DIR
from app.services.planning_service import PlanningService

logger = logging.getLogger("cli_agent.api.agent")

router = APIRouter(prefix="/agent", tags=["Agent"])


@router.post(
    "/plan",
    response_model=PlanGenerateResponse,
    status_code=status.HTTP_200_OK,
    summary="Generate a multi-step task plan (Awaiting Approval)",
)
async def generate_plan(
    payload: PlanGenerateRequest,
    db: Session = Depends(get_db),
) -> PlanGenerateResponse:
    """
    Decomposes a complex user request into an ordered, multi-step execution plan using Groq AI.
    The plan is persisted in SQLite with status 'pending'.
    NO execution occurs until the user approves via POST /api/agent/execute/{plan_id}.
    """
    try:
        task_plan = await PlanningService.create_plan(payload.message, db=db)
        return PlanGenerateResponse(
            success=True,
            plan_id=task_plan.plan_id,
            message="Execution plan generated. Review steps and approve to execute.",
            plan=task_plan,
        )
    except ValueError as e:
        logger.warning("Plan generation rejected: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error("Plan generation error: %s", str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate execution plan due to an internal server error.",
        )


@router.post(
    "/execute/{plan_id}",
    response_model=PlanExecuteResponse,
    status_code=status.HTTP_200_OK,
    summary="Approve and execute a generated task plan",
)
async def execute_plan(
    plan_id: str,
    payload: Optional[PlanExecuteRequest] = None,
    db: Session = Depends(get_db),
) -> PlanExecuteResponse:
    """
    Executes an approved plan step-by-step in topological dependency order.
    Requires explicit user approval. Rejects already running or completed plans.
    """
    if payload and not payload.approved:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Execution approval was explicitly declined.",
        )

    try:
        response = await AgentExecutor.execute_plan(plan_id, db=db)
        return response
    except ValueError as e:
        err_msg = str(e)
        logger.warning("Plan execution rejected for %s: %s", plan_id, err_msg)
        if "not found" in err_msg.lower():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=err_msg)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=err_msg)
    except Exception as e:
        logger.error("Plan execution error for %s: %s", plan_id, str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while executing plan '{plan_id}'.",
        )


@router.post(
    "/cancel/{plan_id}",
    status_code=status.HTTP_200_OK,
    summary="Cancel a pending or running plan",
)
async def cancel_plan(
    plan_id: str,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Cancels a multi-step task plan if it has not already completed.
    """
    plan: Optional[PlanModel] = db.query(PlanModel).filter(PlanModel.id == plan_id).first()
    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Plan '{plan_id}' not found.",
        )

    if plan.status == "completed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Plan '{plan_id}' has already completed and cannot be cancelled.",
        )

    plan.status = "cancelled"
    db.commit()

    return {
        "success": True,
        "plan_id": plan_id,
        "status": "cancelled",
        "message": f"Plan '{plan_id}' was cancelled.",
    }


@router.get(
    "/plans/{plan_id}",
    status_code=status.HTTP_200_OK,
    summary="Get plan details and execution traces",
)
async def get_plan(
    plan_id: str,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Retrieves the current execution status, parameters, and step traces for a plan.
    """
    plan: Optional[PlanModel] = db.query(PlanModel).filter(PlanModel.id == plan_id).first()
    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Plan '{plan_id}' not found.",
        )
    return plan.to_dict()


@router.get(
    "/plans",
    status_code=status.HTTP_200_OK,
    summary="List all plans",
)
async def list_plans(
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> List[Dict[str, Any]]:
    """
    Lists recent multi-step execution plans ordered by creation time descending.
    """
    plans = (
        db.query(PlanModel)
        .order_by(PlanModel.created_at.desc())
        .limit(limit)
        .all()
    )
    return [p.to_dict() for p in plans]


@router.get(
    "/export/{plan_id}",
    summary="Download exported JSON artifact for a completed plan",
)
async def download_export(
    plan_id: str,
    db: Session = Depends(get_db),
):
    """
    Streams the exported JSON file generated by the export_json step.
    """
    # Verify plan exists
    plan: Optional[PlanModel] = db.query(PlanModel).filter(PlanModel.id == plan_id).first()
    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Plan '{plan_id}' not found.",
        )

    file_path = OUTPUT_DIR / f"export_{plan_id}.json"
    if not file_path.is_file():
        # Check if custom filename was specified in steps
        for step in plan.steps:
            if step.operation == "export_json" and step.output_json:
                try:
                    data = json.loads(step.output_json)
                    saved_path = data.get("file_path")
                    if saved_path:
                        candidate_path = Path(saved_path).resolve()
                        # Strictly guarantee candidate file is within OUTPUT_DIR
                        if candidate_path.is_file() and candidate_path.is_relative_to(OUTPUT_DIR.resolve()):
                            file_path = candidate_path
                            break
                except Exception:
                    pass

    if not file_path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Exported artifact file for plan '{plan_id}' not found.",
        )

    return FileResponse(
        path=str(file_path),
        filename=file_path.name,
        media_type="application/json",
    )
