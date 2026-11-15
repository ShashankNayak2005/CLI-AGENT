"""
Multi-Step Planning Service for CLI Agent AI.
Accepts natural-language instructions, uses Groq AI to decompose complex requests into
validated dependency-linked execution steps, and persists plans awaiting human approval.
"""

from datetime import datetime, timezone
import json
import logging
import re
import sys
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session

from app.models.plan import PlanModel, PlanStepModel, generate_plan_id
from app.schemas.plan_schema import PlanStep, TaskPlan
from app.security.url_validator import URLSecurityValidator
from app.services.groq_service import groq_service

logger = logging.getLogger("cli_agent.planner")

PLANNING_SYSTEM_PROMPT = """You are an autonomous task planning engine for CLI Agent AI.
Your role is to decompose complex user instructions into a structured, multi-step execution plan.

Supported Operations:
1. "crawl_website": Crawls a target website within its domain boundaries, extracting text and links.
   Parameters: {"url": "<http or https URL>", "max_pages": 1-10 (default 5), "max_depth": 0-2 (default 1)}
2. "summarize_crawl": Synthesizes an executive summary from previously extracted crawl content.
   Parameters: {} (or {"focus": "<topic to focus on>"})
   Must depend on a crawl_website step.
3. "export_json": Exports the validated crawl and summary data into a safe local JSON file.
   Parameters: {} (or {"filename": "<optional name>"})
   Must depend on a previous crawl_website or summarize_crawl step.

Rules:
- NEVER execute or plan arbitrary shell commands, code execution, or system modifications.
- If the user instruction is unrelated to website crawling/summarization/exporting, return an error goal and empty steps.
- Dependencies must strictly refer to prior step IDs (depends_on: [step_id]).
- Order steps logically: crawl_website (step 1) -> summarize_crawl (step 2) -> export_json (step 3).
- Return RAW JSON only. Do not output markdown code blocks.

Schema:
{
  "goal": "<High-level objective summary>",
  "steps": [
    {
      "step_id": 1,
      "operation": "crawl_website",
      "description": "<What this step will accomplish>",
      "depends_on": [],
      "parameters": {
        "url": "<extracted URL>",
        "max_pages": 5,
        "max_depth": 1
      }
    },
    ...
  ]
}
"""


class PlanningService:
    """
    Decomposes natural language requests into validated multi-step plans.
    """

    @classmethod
    async def create_plan(
        cls,
        user_message: str,
        db: Optional[Session] = None,
    ) -> TaskPlan:
        """
        Generates and validates a TaskPlan from a user prompt.
        If db is provided, persists the plan with status 'pending' awaiting user approval.
        """
        cleaned_msg = user_message.strip()
        if not cleaned_msg:
            raise ValueError("User request message cannot be empty.")

        # Check for explicitly dangerous or unsupported system commands
        dangerous_pattern = re.compile(
            r"\b(delete|remove|bash|exec|powershell|curl|wget|drop\s+table|format\s+[a-z]:|rm\s+-rf|rmdir)\b",
            re.IGNORECASE
        )
        if dangerous_pattern.search(cleaned_msg):
            raise ValueError("Arbitrary system commands or destructive operations are strictly disallowed.")

        plan_id = generate_plan_id()
        created_at = datetime.now(timezone.utc).isoformat()

        raw_plan_dict: Optional[Dict[str, Any]] = None

        # 1. Attempt Groq AI Plan Generation if API key is configured
        client = groq_service._get_client()
        if client:
            try:
                sys.stderr.write(f"[PLANNER] Requesting plan decomposition from Groq AI for: '{cleaned_msg[:60]}...'\n")
                sys.stderr.flush()

                completion = client.chat.completions.create(
                    model=groq_service.model,
                    messages=[
                        {"role": "system", "content": PLANNING_SYSTEM_PROMPT},
                        {"role": "user", "content": cleaned_msg},
                    ],
                    response_format={"type": "json_object"},
                    temperature=0.0,
                    max_tokens=600,
                    timeout=25.0,
                )

                raw_json = completion.choices[0].message.content or "{}"
                raw_plan_dict = json.loads(raw_json)

            except Exception as exc:
                sys.stderr.write(f"[WARN] Groq AI plan generation failed: {str(exc)}. Using rule-based planner.\n")
                sys.stderr.flush()

        # 2. Rule-based Plan Decomposition (fallback or default)
        if not raw_plan_dict or "steps" not in raw_plan_dict or not raw_plan_dict["steps"]:
            raw_plan_dict = cls._decompose_rule_based(cleaned_msg)

        # 3. Assemble and Validate with Pydantic TaskPlan schema
        raw_plan_dict["plan_id"] = plan_id
        raw_plan_dict["user_request"] = cleaned_msg
        raw_plan_dict["status"] = "pending"
        raw_plan_dict["created_at"] = created_at

        # Ensure each step has required fields
        for idx, step in enumerate(raw_plan_dict.get("steps", []), 1):
            if "step_id" not in step:
                step["step_id"] = idx
            if "status" not in step:
                step["status"] = "pending"
            if "duration_seconds" not in step:
                step["duration_seconds"] = 0.0

        task_plan = TaskPlan.model_validate(raw_plan_dict)

        # 4. Persist Plan in Database (if session provided)
        if db is not None:
            cls.persist_plan(db, task_plan)

        return task_plan

    @classmethod
    def persist_plan(cls, db: Session, plan: TaskPlan) -> PlanModel:
        """
        Saves a validated TaskPlan and its steps in the SQLite database.
        """
        plan_model = PlanModel(
            id=plan.plan_id,
            goal=plan.goal,
            user_request=plan.user_request,
            status=plan.status,
            plan_json=plan.model_dump_json(),
            created_at=datetime.fromisoformat(plan.created_at),
        )

        db.add(plan_model)
        db.flush()

        for step in plan.steps:
            step_model = PlanStepModel(
                plan_id=plan.plan_id,
                step_id=step.step_id,
                operation=step.operation,
                description=step.description,
                depends_on_json=json.dumps(step.depends_on),
                parameters_json=json.dumps(step.parameters),
                status=step.status,
                duration_seconds=step.duration_seconds,
            )
            db.add(step_model)

        db.commit()
        db.refresh(plan_model)
        logger.info("Persisted plan '%s' with %d steps in SQLite.", plan.plan_id, len(plan.steps))
        return plan_model

    @classmethod
    def _decompose_rule_based(cls, text: str) -> Dict[str, Any]:
        """
        Intelligent rule-based plan generator for offline operation or fallback.
        """
        # Detect any HTTP/HTTPS URL or domain candidates in text
        raw_matches = re.findall(r"https?://[^\s<>\"']+", text)
        if not raw_matches:
            raw_matches = re.findall(
                r"\b(?:www\.[-a-zA-Z0-9@:%._\+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}|"
                r"[-a-zA-Z0-9@:%._\+~#=]{1,256}\.(?:com|org|net|edu|gov|io|ai|co|in|info|biz|me|dev|app|org\.in|co\.in|ac\.in))\b(?:[-a-zA-Z0-9()@:%_\+.~#?&//=]*)",
                text,
                re.IGNORECASE,
            )

        if raw_matches:
            first_raw = raw_matches[0].rstrip(".,;:!?'\")>]}")
            is_valid, reason, norm_url = URLSecurityValidator.validate_url(first_raw)
            if not is_valid:
                raise ValueError(f"URL security validation failed: {reason}")
            target_url = norm_url
        else:
            urls = groq_service.extract_urls(text)
            if not urls:
                raise ValueError("No valid HTTP/HTTPS URL found in request. Multi-step workflows require a target website.")
            target_url = urls[0]

        lower = text.lower()

        # Parse custom limits if user requested them
        max_pages = 5
        pages_match = re.search(r"(\d+)\s*(?:pages?|sites?|links?)", lower)
        if pages_match:
            try:
                max_pages = max(1, min(int(pages_match.group(1)), 10))
            except ValueError:
                pass

        max_depth = 1
        depth_match = re.search(r"depth\s*(\d+)", lower)
        if depth_match:
            try:
                max_depth = max(0, min(int(depth_match.group(1)), 2))
            except ValueError:
                pass

        steps: List[Dict[str, Any]] = []

        # Step 1: crawl_website is always the initial root step
        steps.append({
            "step_id": 1,
            "operation": "crawl_website",
            "description": f"Crawl {target_url} up to {max_pages} pages (depth {max_depth}) and extract clean text and links.",
            "depends_on": [],
            "parameters": {
                "url": target_url,
                "max_pages": max_pages,
                "max_depth": max_depth,
            },
        })

        # Step 2: summarize_crawl if user mentioned summarize, overview, analyze, or important info
        wants_summary = any(kw in lower for kw in ["summarize", "summary", "overview", "important", "analyze", "key points", "extract"])
        last_step_id = 1
        if wants_summary or len(steps) == 1:
            steps.append({
                "step_id": 2,
                "operation": "summarize_crawl",
                "description": "Synthesize a structured summary with key points and source URLs from extracted content.",
                "depends_on": [1],
                "parameters": {},
            })
            last_step_id = 2

        # Step 3: export_json if user mentioned save, export, json, download, or file
        wants_export = any(kw in lower for kw in ["export", "save", "download", "json", "file", "store", "persist"])
        if wants_export:
            steps.append({
                "step_id": len(steps) + 1,
                "operation": "export_json",
                "description": "Save validated crawl telemetry and executive summary into an application-controlled JSON file.",
                "depends_on": [last_step_id],
                "parameters": {},
            })

        return {
            "goal": f"Extract, analyze, and process content from {target_url}",
            "steps": steps,
        }


planning_service = PlanningService()
