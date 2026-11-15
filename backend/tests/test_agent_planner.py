"""
Unit and Integration Tests for Phase 5: Multi-Step AI Agent.
Tests plan generation, topological graph validation, security constraints,
summarization, dependency execution, replay protection, cancellation, and API endpoints.
"""

from datetime import datetime, timezone
import json
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.models.database import Base, get_db
from app.models.plan import PlanModel, PlanStepModel, generate_plan_id
from app.schemas.crawl_schema import CrawlResult, HeadingItem, PageCrawlResult, WebsiteSummary
from app.schemas.plan_schema import PlanStep, TaskPlan
from app.services.agent_executor import AgentExecutor, OUTPUT_DIR
from app.services.crawl_service import crawl_service
from app.services.planning_service import PlanningService
from app.services.summarization_service import SummarizationService


@pytest.fixture
def agent_test_env(tmp_path):
    """Sets up an isolated SQLite database and FastAPI TestClient for agent tests."""
    db_file = tmp_path / "test_agent.db"
    db_url = f"sqlite:///{db_file.as_posix()}"
    engine = create_engine(db_url, connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    def override_get_db():
        session = TestingSession()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)

    yield client, TestingSession

    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)


# -----------------------------------------------------------------------------
# Plan Schema & Graph Validation Tests
# -----------------------------------------------------------------------------

def test_valid_task_plan_schema():
    """Verify that a properly constructed TaskPlan validates successfully."""
    plan = TaskPlan(
        plan_id="plan_test1",
        goal="Crawl, summarize and export",
        user_request="Crawl https://example.com and export summary",
        status="pending",
        created_at=datetime.now(timezone.utc).isoformat(),
        steps=[
            PlanStep(
                step_id=1,
                operation="crawl_website",
                description="Crawl example.com",
                depends_on=[],
                parameters={"url": "https://example.com", "max_pages": 3, "max_depth": 1},
            ),
            PlanStep(
                step_id=2,
                operation="summarize_crawl",
                description="Summarize crawl content",
                depends_on=[1],
                parameters={},
            ),
            PlanStep(
                step_id=3,
                operation="export_json",
                description="Export result",
                depends_on=[2],
                parameters={"filename": "example_summary.json"},
            ),
        ],
    )
    assert plan.plan_id == "plan_test1"
    assert len(plan.steps) == 3
    # Normalizer standardizes domain root with trailing slash
    assert plan.steps[0].parameters["url"] == "https://example.com/"


def test_disallowed_operation_rejected():
    """Verify that operations outside the approved registry are strictly rejected."""
    with pytest.raises(Exception):
        PlanStep(
            step_id=1,
            operation="execute_shell_script",  # Disallowed
            depends_on=[],
            parameters={"cmd": "dir"},
        )


def test_self_dependency_rejected():
    """Verify that a step cannot depend on itself."""
    with pytest.raises(ValueError, match="cannot depend on itself"):
        TaskPlan(
            plan_id="plan_self_dep",
            goal="Test self dependency",
            user_request="test",
            status="pending",
            created_at=datetime.now(timezone.utc).isoformat(),
            steps=[
                PlanStep(
                    step_id=1,
                    operation="crawl_website",
                    depends_on=[1],  # Self-dependency!
                    parameters={"url": "https://example.com"},
                ),
            ],
        )


def test_forward_or_circular_dependency_rejected():
    """Verify that forward or circular dependencies are rejected."""
    with pytest.raises(ValueError, match="Dependencies must strictly precede"):
        TaskPlan(
            plan_id="plan_circ",
            goal="Test circular dependency",
            user_request="test",
            status="pending",
            created_at=datetime.now(timezone.utc).isoformat(),
            steps=[
                PlanStep(
                    step_id=1,
                    operation="crawl_website",
                    depends_on=[2],  # Forward reference to step 2!
                    parameters={"url": "https://example.com"},
                ),
                PlanStep(
                    step_id=2,
                    operation="summarize_crawl",
                    depends_on=[1],
                    parameters={},
                ),
            ],
        )


def test_ssrf_url_in_crawl_step_rejected():
    """Verify that crawl_website steps with private or loopback URLs are rejected by plan validator."""
    with pytest.raises(ValueError, match="URL security validation failed"):
        TaskPlan(
            plan_id="plan_ssrf",
            goal="Test SSRF rejection in plan",
            user_request="test",
            status="pending",
            created_at=datetime.now(timezone.utc).isoformat(),
            steps=[
                PlanStep(
                    step_id=1,
                    operation="crawl_website",
                    depends_on=[],
                    parameters={"url": "http://127.0.0.1:8000/secret"},
                ),
            ],
        )


# -----------------------------------------------------------------------------
# Planning Service Tests
# -----------------------------------------------------------------------------

@pytest.mark.anyio
async def test_planning_service_rule_based_fallback(agent_test_env):
    """Verify that the planning service creates a valid 3-step plan from natural language."""
    _, TestingSession = agent_test_env
    db = TestingSession()
    try:
        prompt = "Visit https://example.com, extract the important info, summarize it, and save the result as JSON."
        plan = await PlanningService.create_plan(prompt, db=db)
        assert plan.plan_id.startswith("plan_")
        assert len(plan.steps) == 3
        assert plan.steps[0].operation == "crawl_website"
        assert plan.steps[0].parameters["url"] == "https://example.com/"
        assert plan.steps[1].operation == "summarize_crawl"
        assert plan.steps[1].depends_on == [1]
        assert plan.steps[2].operation == "export_json"
        assert plan.steps[2].depends_on == [2]

        # Verify persisted in DB
        db_plan = db.query(PlanModel).filter(PlanModel.id == plan.plan_id).first()
        assert db_plan is not None
        assert db_plan.status == "pending"
        assert len(db_plan.steps) == 3
    finally:
        db.close()


@pytest.mark.anyio
async def test_planning_service_rejects_dangerous_commands(agent_test_env):
    """Verify that destructive/shell instructions are strictly blocked."""
    _, TestingSession = agent_test_env
    db = TestingSession()
    try:
        with pytest.raises(ValueError, match="Arbitrary system commands or destructive operations are strictly disallowed"):
            await PlanningService.create_plan("Please delete all files in system32 and powershell format c:", db=db)
    finally:
        db.close()


# -----------------------------------------------------------------------------
# Summarization Service Tests
# -----------------------------------------------------------------------------

@pytest.mark.anyio
async def test_summarization_service_grounded_fallback():
    """Verify summarizer produces structured summary grounded strictly in crawl content."""
    mock_crawl = CrawlResult(
        success=True,
        status="completed",
        target_url="https://example.com",
        pages_crawled=1,
        pages_failed=0,
        execution_time_seconds=0.1,
        website_summary=WebsiteSummary(title="Example Domain", description="Illustrative example domain"),
        pages=[
            PageCrawlResult(
                url="https://example.com",
                status_code=200,
                title="Example Domain",
                description="Illustrative example domain",
                headings=[HeadingItem(level="h1", text="Example Domain")],
                main_content=[
                    "This domain is for use in illustrative examples in documents.",
                    "You may use this domain in literature without prior coordination or asking for permission.",
                ],
                internal_links=[],
                external_links=[],
                word_count=25,
                crawled_at=datetime.now(timezone.utc).isoformat(),
            )
        ],
        errors=[],
    )

    summary = await SummarizationService.summarize_crawl(mock_crawl)
    assert summary.website_title == "Example Domain"
    assert "https://example.com" in summary.source_urls
    assert len(summary.key_points) > 0
    assert len(summary.overview) > 0


@pytest.mark.anyio
async def test_summarization_service_empty_crawl():
    """Verify summarizer handles empty crawl results gracefully without errors."""
    empty_crawl = CrawlResult(
        success=False,
        status="failed",
        target_url="https://example.com",
        pages_crawled=0,
        pages_failed=0,
        execution_time_seconds=0.0,
        website_summary=WebsiteSummary(),
        pages=[],
        errors=[],
    )
    summary = await SummarizationService.summarize_crawl(empty_crawl)
    assert "No webpage content" in summary.limitations[0]


# -----------------------------------------------------------------------------
# Agent Executor & Human-in-the-Loop Tests
# -----------------------------------------------------------------------------

@pytest.mark.anyio
async def test_agent_executor_full_flow(agent_test_env, monkeypatch):
    """Test end-to-end plan execution with mocked crawl service."""
    _, TestingSession = agent_test_env
    db = TestingSession()
    try:
        mock_result = CrawlResult(
            success=True,
            status="completed",
            target_url="https://example.com",
            pages_crawled=1,
            pages_failed=0,
            execution_time_seconds=0.2,
            website_summary=WebsiteSummary(title="Example Domain", description="Example meta description"),
            pages=[
                PageCrawlResult(
                    url="https://example.com",
                    status_code=200,
                    title="Example Domain",
                    description="Example meta description",
                    headings=[HeadingItem(level="h1", text="Example Heading")],
                    main_content=["Example paragraph content."],
                    internal_links=[],
                    external_links=[],
                    word_count=10,
                    crawled_at=datetime.now(timezone.utc).isoformat(),
                )
            ],
            errors=[],
        )

        async def mock_crawl(*args, **kwargs):
            return mock_result

        monkeypatch.setattr(crawl_service, "crawl", mock_crawl)

        # 1. Create Plan
        prompt = "Visit https://example.com, summarize it, and export JSON"
        plan = await PlanningService.create_plan(prompt, db=db)

        # 2. Execute Plan
        exec_response = await AgentExecutor.execute_plan(plan.plan_id, db=db)

        assert exec_response.success is True
        assert exec_response.status == "completed"
        assert len(exec_response.steps) == 3
        assert all(s.status == "completed" for s in exec_response.steps)
        assert exec_response.final_result is not None
        assert "summary" in exec_response.final_result or "export" in exec_response.final_result

        # Verify DB updated
        db_plan = db.query(PlanModel).filter(PlanModel.id == plan.plan_id).first()
        assert db_plan.status == "completed"
        assert db_plan.completed_at is not None

        # 3. Prevent Replay: Executing again must fail
        with pytest.raises(ValueError, match="already been executed"):
            await AgentExecutor.execute_plan(plan.plan_id, db=db)

    finally:
        db.close()


@pytest.mark.anyio
async def test_agent_executor_handles_step_failure(agent_test_env, monkeypatch):
    """Verify that when a step fails, subsequent dependent steps are skipped."""
    _, TestingSession = agent_test_env
    db = TestingSession()
    try:
        async def failing_crawl(*args, **kwargs):
            raise ConnectionError("Simulated network timeout during crawl")

        monkeypatch.setattr(crawl_service, "crawl", failing_crawl)

        prompt = "Visit https://example.com, summarize it, and export JSON"
        plan = await PlanningService.create_plan(prompt, db=db)

        exec_response = await AgentExecutor.execute_plan(plan.plan_id, db=db)

        assert exec_response.success is False
        assert exec_response.status == "failed"
        assert exec_response.steps[0].status == "failed"
        assert exec_response.steps[1].status == "skipped"
        assert exec_response.steps[2].status == "skipped"

    finally:
        db.close()


# -----------------------------------------------------------------------------
# Agent API Endpoint Tests
# -----------------------------------------------------------------------------

def test_api_generate_plan_endpoint(agent_test_env):
    """Verify POST /api/agent/plan creates a plan in pending status."""
    client, _ = agent_test_env
    response = client.post(
        "/api/agent/plan",
        json={"message": "Visit https://example.com, summarize it, and export JSON"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "plan_id" in data
    assert data["plan"]["status"] == "pending"
    assert len(data["plan"]["steps"]) == 3


def test_api_cancel_plan_endpoint(agent_test_env):
    """Verify POST /api/agent/cancel/{plan_id} marks plan as cancelled."""
    client, _ = agent_test_env
    gen_res = client.post(
        "/api/agent/plan",
        json={"message": "Visit https://example.com, summarize it, and export JSON"},
    )
    plan_id = gen_res.json()["plan_id"]

    cancel_res = client.post(f"/api/agent/cancel/{plan_id}")
    assert cancel_res.status_code == 200
    assert cancel_res.json()["status"] == "cancelled"

    # Execution of cancelled plan must fail
    exec_res = client.post(f"/api/agent/execute/{plan_id}", json={"approved": True})
    assert exec_res.status_code == 400
    data = exec_res.json()
    error_text = (data.get("message") or data.get("detail", "")).lower()
    assert "cancelled" in error_text


def test_api_execute_plan_endpoint(agent_test_env, monkeypatch):
    """Verify POST /api/agent/execute/{plan_id} executes with approval."""
    client, _ = agent_test_env

    mock_result = CrawlResult(
        success=True,
        status="completed",
        target_url="https://example.com",
        pages_crawled=1,
        pages_failed=0,
        execution_time_seconds=0.1,
        website_summary=WebsiteSummary(title="Example", description="desc"),
        pages=[
            PageCrawlResult(
                url="https://example.com",
                status_code=200,
                title="Example",
                description="desc",
                headings=[],
                main_content=["Sample content"],
                internal_links=[],
                external_links=[],
                word_count=5,
                crawled_at=datetime.now(timezone.utc).isoformat(),
            )
        ],
        errors=[],
    )

    async def mock_crawl(*args, **kwargs):
        return mock_result

    monkeypatch.setattr(crawl_service, "crawl", mock_crawl)

    gen_res = client.post(
        "/api/agent/plan",
        json={"message": "Visit https://example.com, summarize it, and export JSON"},
    )
    plan_id = gen_res.json()["plan_id"]

    exec_res = client.post(f"/api/agent/execute/{plan_id}", json={"approved": True})
    assert exec_res.status_code == 200
    exec_data = exec_res.json()
    assert exec_data["success"] is True
    assert exec_data["status"] == "completed"

    # Verify GET /api/agent/plans/{plan_id}
    get_res = client.get(f"/api/agent/plans/{plan_id}")
    assert get_res.status_code == 200
    assert get_res.json()["status"] == "completed"

    # Verify GET /api/agent/export/{plan_id}
    export_res = client.get(f"/api/agent/export/{plan_id}")
    assert export_res.status_code == 200
    assert export_res.headers["content-type"] == "application/json"
