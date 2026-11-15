"""
Controlled Multi-Step Agent Execution Engine.
Executes approved task plans in strict dependency order using an explicit operation registry.
Tracks live execution traces, enforces timeouts, captures outputs, and updates persistent SQLite records.
"""

from datetime import datetime, timezone
import json
import logging
from pathlib import Path
import sys
import time
from typing import Any, Callable, Dict, List, Optional
from sqlalchemy.orm import Session

from app.config import BASE_DIR
from app.models.plan import PlanModel, PlanStepModel
from app.schemas.crawl_schema import CrawlResult
from app.schemas.plan_schema import PlanExecuteResponse, StepExecutionResult, TaskPlan
from app.services.crawl_service import crawl_service
from app.services.summarization_service import summarization_service

logger = logging.getLogger("cli_agent.agent_executor")

# Output directory for exported JSON files (strictly controlled application directory)
OUTPUT_DIR = BASE_DIR / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


class AgentExecutor:
    """
    Executes approved multi-step TaskPlan graphs.
    """

    @classmethod
    async def execute_plan(
        cls,
        plan_id: str,
        db: Session,
        timeout_seconds: float = 120.0,
    ) -> PlanExecuteResponse:
        """
        Executes a previously generated and user-approved plan.
        Rejects replay attempts on already executed plans.
        """
        start_plan_time = time.perf_counter()

        # 1. Fetch Plan from Database
        plan_model: Optional[PlanModel] = db.query(PlanModel).filter(PlanModel.id == plan_id).first()
        if not plan_model:
            raise ValueError(f"Plan '{plan_id}' not found.")

        # 2. Prevent Replay or Duplicate Execution
        if plan_model.status in ("running", "completed"):
            raise ValueError(f"Plan '{plan_id}' has already been executed or is currently running (status: {plan_model.status}).")

        if plan_model.status == "cancelled":
            raise ValueError(f"Plan '{plan_id}' was cancelled by the user and cannot be executed.")

        # 3. Mark Plan as Running
        plan_model.status = "running"
        plan_model.approved_at = datetime.now(timezone.utc)
        db.commit()

        # Deserialized plan schema
        plan_data = json.loads(plan_model.plan_json)
        task_plan = TaskPlan.model_validate(plan_data)

        # Context memory storing outputs produced by previous steps: {step_id: output_dict}
        step_outputs: Dict[int, Any] = {}
        step_results: List[StepExecutionResult] = []
        plan_failed = False
        final_result_payload: Dict[str, Any] = {}

        # 4. Execute Steps in Sequential Dependency Order
        for step in task_plan.steps:
            step_model: Optional[PlanStepModel] = (
                db.query(PlanStepModel)
                .filter(PlanStepModel.plan_id == plan_id, PlanStepModel.step_id == step.step_id)
                .first()
            )

            # Check if all required dependencies succeeded
            deps_met = True
            for dep_id in step.depends_on:
                dep_output = step_outputs.get(dep_id)
                dep_step_res = next((r for r in step_results if r.step_id == dep_id), None)
                if not dep_step_res or dep_step_res.status != "completed":
                    deps_met = False
                    break

            if not deps_met or plan_failed:
                # Skip step because dependency failed or earlier step halted plan
                sys.stderr.write(f"[AGENT] Skipping Step {step.step_id} ({step.operation}) due to dependency failure.\n")
                sys.stderr.flush()

                step_res = StepExecutionResult(
                    step_id=step.step_id,
                    operation=step.operation,
                    status="skipped",
                    duration_seconds=0.0,
                    error="Skipped because required dependency failed or did not run.",
                )
                step_results.append(step_res)

                if step_model:
                    step_model.status = "skipped"
                    step_model.error_message = step_res.error
                    db.commit()
                continue

            # Execute Step
            step_start = time.perf_counter()
            if step_model:
                step_model.status = "running"
                step_model.started_at = datetime.now(timezone.utc)
                db.commit()

            sys.stderr.write(f"[AGENT] Executing Step {step.step_id}/{len(task_plan.steps)}: {step.operation}...\n")
            sys.stderr.flush()

            try:
                output_data = await cls._dispatch_operation(
                    operation=step.operation,
                    parameters=step.parameters,
                    step_outputs=step_outputs,
                    plan_id=plan_id,
                )
                step_duration = round(time.perf_counter() - step_start, 2)
                step_outputs[step.step_id] = output_data

                step_res = StepExecutionResult(
                    step_id=step.step_id,
                    operation=step.operation,
                    status="completed",
                    duration_seconds=step_duration,
                    output=output_data,
                )
                step_results.append(step_res)

                if step_model:
                    step_model.status = "completed"
                    step_model.duration_seconds = step_duration
                    step_model.output_json = json.dumps(output_data)
                    step_model.completed_at = datetime.now(timezone.utc)
                    db.commit()

                # Keep track of prominent outputs for final payload
                if step.operation == "crawl_website":
                    final_result_payload["crawl"] = output_data
                elif step.operation == "summarize_crawl":
                    final_result_payload["summary"] = output_data
                elif step.operation == "export_json":
                    final_result_payload["export"] = output_data

            except Exception as exc:
                step_duration = round(time.perf_counter() - step_start, 2)
                err_msg = str(exc)
                sys.stderr.write(f"[AGENT] Step {step.step_id} ({step.operation}) failed: {err_msg}\n")
                sys.stderr.flush()

                plan_failed = True
                step_res = StepExecutionResult(
                    step_id=step.step_id,
                    operation=step.operation,
                    status="failed",
                    duration_seconds=step_duration,
                    error=err_msg,
                )
                step_results.append(step_res)

                if step_model:
                    step_model.status = "failed"
                    step_model.duration_seconds = step_duration
                    step_model.error_message = err_msg
                    step_model.completed_at = datetime.now(timezone.utc)
                    db.commit()

        total_duration = round(time.perf_counter() - start_plan_time, 2)
        final_status = "failed" if plan_failed else "completed"

        # 5. Update Plan Database Record
        plan_model.status = final_status
        plan_model.total_duration = total_duration
        plan_model.completed_at = datetime.now(timezone.utc)
        plan_model.final_result_json = json.dumps(final_result_payload)
        if plan_failed:
            plan_model.error_message = next((s.error for s in step_results if s.error), "Execution step failed")
        db.commit()

        message = (
            "Multi-step agent plan completed successfully."
            if final_status == "completed"
            else "Plan execution completed with step failures."
        )

        sys.stderr.write(f"[AGENT] Plan {plan_id} {final_status} in {total_duration}s\n")
        sys.stderr.flush()

        return PlanExecuteResponse(
            success=(final_status == "completed"),
            plan_id=plan_id,
            status=final_status,
            message=message,
            total_duration=total_duration,
            steps=step_results,
            final_result=final_result_payload,
        )

    @classmethod
    async def _dispatch_operation(
        cls,
        operation: str,
        parameters: Dict[str, Any],
        step_outputs: Dict[int, Any],
        plan_id: str,
    ) -> Dict[str, Any]:
        """
        Strict Operation Registry.
        Directs execution ONLY to approved operations without arbitrary code execution.
        """
        if operation == "crawl_website":
            url = parameters["url"]
            max_pages = parameters.get("max_pages", 5)
            max_depth = parameters.get("max_depth", 1)
            timeout = parameters.get("timeout", 15.0)

            crawl_res = await crawl_service.crawl(
                target_url=url,
                max_pages=max_pages,
                max_depth=max_depth,
                timeout=timeout,
            )

            if crawl_res.pages_crawled == 0:
                err_msg = crawl_res.errors[0].message if crawl_res.errors else "No pages could be crawled."
                raise RuntimeError(f"Crawl failed: {err_msg}")

            return crawl_res.model_dump()

        elif operation == "summarize_crawl":
            # Retrieve preceding crawl result from context
            crawl_data = None
            for out in step_outputs.values():
                if isinstance(out, dict) and "pages_crawled" in out:
                    crawl_data = out
                    break

            if not crawl_data:
                raise RuntimeError("Cannot summarize crawl: No crawl output found from preceding steps.")

            crawl_obj = CrawlResult.model_validate(crawl_data)
            summary_res = await summarization_service.summarize_crawl(
                crawl_result=crawl_obj,
                focus=parameters.get("focus"),
            )
            return summary_res.model_dump()

        elif operation == "export_json":
            # Gather all preceding outputs to export into a safe JSON file
            export_payload = {
                "plan_id": plan_id,
                "exported_at": datetime.now(timezone.utc).isoformat(),
                "steps_data": step_outputs,
            }

            filename = f"export_{plan_id}.json"
            if parameters.get("filename"):
                clean_name = "".join(c for c in parameters["filename"] if c.isalnum() or c in ("-", "_"))
                if clean_name:
                    filename = f"{clean_name}_{plan_id}.json"

            file_path = (OUTPUT_DIR / filename).resolve()
            # Enforce path traversal defense
            if not file_path.is_relative_to(OUTPUT_DIR.resolve()):
                raise ValueError("Path traversal attempt detected in export filename.")

            json_str = json.dumps(export_payload, indent=2)

            file_path.write_text(json_str, encoding="utf-8")
            file_size = len(json_str.encode("utf-8"))

            sys.stderr.write(f"[AGENT] Exported validated JSON to: {file_path} ({file_size} bytes)\n")
            sys.stderr.flush()

            return {
                "file_path": str(file_path),
                "filename": filename,
                "file_size_bytes": file_size,
                "exported_successfully": True,
            }

        else:
            raise ValueError(f"Unauthorized or unknown operation '{operation}' in execution registry.")


agent_executor = AgentExecutor()
