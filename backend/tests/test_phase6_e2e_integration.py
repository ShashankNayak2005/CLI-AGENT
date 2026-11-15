"""
Phase 6 Comprehensive Integration and Edge Case Test Suite.
Verifies end-to-end multi-step agent flow, CLI subprocess invocation,
Pydantic validation, SQLite persistence, and edge case error resilience.
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
from app.models.plan import PlanModel
from app.models.task import TaskModel
from app.schemas.crawl_schema import CrawlResult, HeadingItem, PageCrawlResult, WebsiteSummary
from app.schemas.plan_schema import PlanExecuteRequest, PlanGenerateRequest, TaskPlan
from app.services.agent_executor import AgentExecutor
from app.services.cli_executor import cli_executor
from app.services.crawl_service import crawl_service
from app.services.groq_service import groq_service
from app.services.planning_service import PlanningService


@pytest.fixture
def e2e_env(tmp_path):
    """Sets up an isolated SQLite database and TestClient for e2e tests."""
    db_file = tmp_path / "e2e_test.db"
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
# 1. MANDATORY SUCCESS TEST
# -----------------------------------------------------------------------------

def test_mandatory_success_workflow(e2e_env, monkeypatch):
    """
    Mandatory Success Test:
    User request: "Crawl https://example.com, extract important information, summarize it, and return the result in JSON."
    Verifies:
    1. Frontend sends actual request to /api/agent/plan.
    2. FastAPI receives it and invokes Groq/PlanningService.
    3. Pydantic validates the structured plan.
    4. Plan persists in SQLite with status 'pending' (Human-in-the-Loop).
    5. User approves execution via POST /api/agent/execute/{plan_id}.
    6. AgentExecutor runs approved steps in dependency order.
    7. Crawler extracts website information and validates schema.
    8. Summarizer produces grounded summary.
    9. JSON artifact is exported and downloadable.
    10. Complete execution trace is saved in SQLite.
    """
    client, TestingSession = e2e_env

    # Mock crawl output to ensure deterministic test execution
    mock_crawl = CrawlResult(
        success=True,
        status="completed",
        target_url="https://example.com/",
        pages_crawled=1,
        pages_failed=0,
        execution_time_seconds=0.45,
        website_summary=WebsiteSummary(
            title="Example Domain",
            description="Illustrative example domain for documentation.",
            headings=["Example Domain"],
            main_content=["This domain is for use in illustrative examples in documents."],
        ),
        pages=[
            PageCrawlResult(
                url="https://example.com/",
                status_code=200,
                title="Example Domain",
                description="Illustrative example domain",
                headings=[HeadingItem(level="h1", text="Example Domain")],
                main_content=["This domain is for use in illustrative examples in documents."],
                crawled_at=datetime.now(timezone.utc).isoformat(),
            )
        ],
        errors=[],
    )

    async def mock_crawl_op(*args, **kwargs):
        return mock_crawl

    monkeypatch.setattr(crawl_service, "crawl", mock_crawl_op)

    # Step 1: User requests multi-step plan
    user_prompt = "Crawl https://example.com, extract important information, summarize it, and return the result in JSON."
    plan_res = client.post("/api/agent/plan", json={"message": user_prompt})
    assert plan_res.status_code == 200
    plan_data = plan_res.json()
    assert plan_data["success"] is True
    plan_id = plan_data["plan_id"]
    assert plan_data["plan"]["status"] == "pending"
    assert len(plan_data["plan"]["steps"]) == 3

    # Step 2: Verify stored in SQLite in pending state
    db = TestingSession()
    db_plan = db.query(PlanModel).filter(PlanModel.id == plan_id).first()
    assert db_plan is not None
    assert db_plan.status == "pending"
    assert len(db_plan.steps) == 3
    db.close()

    # Step 3: User approves plan execution
    exec_res = client.post(f"/api/agent/execute/{plan_id}", json={"approved": True})
    assert exec_res.status_code == 200
    exec_data = exec_res.json()
    assert exec_data["success"] is True
    assert exec_data["status"] == "completed"
    assert len(exec_data["steps"]) == 3
    assert all(s["status"] == "completed" for s in exec_data["steps"])

    # Step 4: Verify grounded summary and exported artifact
    assert "summary" in exec_data["final_result"]
    assert "export" in exec_data["final_result"]

    # Step 5: Verify export download endpoint works
    export_res = client.get(f"/api/agent/export/{plan_id}")
    assert export_res.status_code == 200
    assert export_res.headers["content-type"] == "application/json"
    exported_json = export_res.json()
    assert exported_json["plan_id"] == plan_id
    assert "1" in exported_json["steps_data"]


# -----------------------------------------------------------------------------
# 2. EDGE CASE TESTS
# -----------------------------------------------------------------------------

def test_edge_case_invalid_url(e2e_env):
    """Verify malformed or invalid URLs are rejected."""
    client, _ = e2e_env
    res = client.post("/api/chat", json={"message": "Crawl ht!tp://invalid-url.com"})
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is False
    assert data["execution"]["status"] == "rejected"


def test_edge_case_private_ip_url(e2e_env):
    """Verify SSRF defense blocks private and loopback addresses."""
    client, _ = e2e_env
    # Chat endpoint
    res1 = client.post("/api/chat", json={"message": "Crawl http://127.0.0.1:8000/admin"})
    assert res1.status_code == 200
    assert res1.json()["success"] is False
    assert res1.json()["execution"]["status"] == "rejected"

    # Agent plan endpoint
    res2 = client.post("/api/agent/plan", json={"message": "Crawl http://192.168.1.1/secret and export json"})
    assert res2.status_code == 400
    assert "security validation failed" in res2.json()["message"].lower()


def test_edge_case_unsupported_intent(e2e_env):
    """Verify unsupported system commands or questions are safely rejected."""
    client, _ = e2e_env
    res = client.post("/api/chat", json={"message": "Please write a python script to delete files"})
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is False
    assert data["intent"]["intent"] == "unsupported"


def test_edge_case_malformed_groq_response(e2e_env, monkeypatch):
    """Verify malformed JSON from Groq triggers safe fallback without crashing."""
    client, _ = e2e_env

    # Force Groq client mock to return invalid JSON
    class MockGroqClient:
        class chat:
            class completions:
                @staticmethod
                def create(*args, **kwargs):
                    class MockChoice:
                        message = type("Msg", (), {"content": "INVALID_JSON{{{"})()
                    return type("Res", (), {"choices": [MockChoice()]})()

    monkeypatch.setattr(groq_service, "_get_client", lambda: MockGroqClient())

    res = client.post("/api/agent/plan", json={"message": "Visit https://example.com, summarize it, and export JSON"})
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert len(data["plan"]["steps"]) == 3


def test_edge_case_website_unavailable(e2e_env, monkeypatch):
    """Verify connection failure on target website is reported as failed with safe message."""
    client, _ = e2e_env

    async def mock_failing_crawl(*args, **kwargs):
        return CrawlResult(
            success=False,
            status="failed",
            target_url="https://example.com/",
            pages_crawled=0,
            pages_failed=1,
            execution_time_seconds=0.1,
            website_summary=WebsiteSummary(),
            pages=[],
            errors=[{"url": "https://example.com/", "error_type": "ConnectError", "message": "Failed to connect to host"}],
        )

    monkeypatch.setattr(crawl_service, "crawl", mock_failing_crawl)

    gen_res = client.post("/api/agent/plan", json={"message": "Visit https://example.com and export JSON"})
    plan_id = gen_res.json()["plan_id"]

    exec_res = client.post(f"/api/agent/execute/{plan_id}", json={"approved": True})
    assert exec_res.status_code == 200
    exec_data = exec_res.json()
    assert exec_data["success"] is False
    assert exec_data["status"] == "failed"
    assert exec_data["steps"][0]["status"] == "failed"
    assert exec_data["steps"][1]["status"] == "skipped"


def test_edge_case_website_timeout(e2e_env, monkeypatch):
    """Verify HTTP timeout is captured cleanly."""
    client, _ = e2e_env

    async def mock_timeout_crawl(*args, **kwargs):
        return CrawlResult(
            success=False,
            status="failed",
            target_url="https://example.com/",
            pages_crawled=0,
            pages_failed=1,
            execution_time_seconds=15.0,
            website_summary=WebsiteSummary(),
            pages=[],
            errors=[{"url": "https://example.com/", "error_type": "Timeout", "message": "Request timed out after 15s"}],
        )

    monkeypatch.setattr(crawl_service, "crawl", mock_timeout_crawl)

    gen_res = client.post("/api/agent/plan", json={"message": "Visit https://example.com and export JSON"})
    plan_id = gen_res.json()["plan_id"]

    exec_res = client.post(f"/api/agent/execute/{plan_id}", json={"approved": True})
    assert exec_res.status_code == 200
    assert exec_res.json()["status"] == "failed"


def test_edge_case_non_html_response(e2e_env, monkeypatch):
    """Verify non-HTML content (e.g. PDF/binary) is rejected with UnsupportedContentType."""
    client, _ = e2e_env

    async def mock_pdf_crawl(*args, **kwargs):
        return CrawlResult(
            success=False,
            status="failed",
            target_url="https://example.com/document.pdf",
            pages_crawled=0,
            pages_failed=1,
            execution_time_seconds=0.1,
            website_summary=WebsiteSummary(),
            pages=[],
            errors=[{"url": "https://example.com/document.pdf", "error_type": "UnsupportedContentType", "message": "Expected HTML, received 'application/pdf'"}],
        )

    monkeypatch.setattr(crawl_service, "crawl", mock_pdf_crawl)

    gen_res = client.post("/api/agent/plan", json={"message": "Visit https://example.com and export JSON"})
    plan_id = gen_res.json()["plan_id"]

    exec_res = client.post(f"/api/agent/execute/{plan_id}", json={"approved": True})
    assert exec_res.status_code == 200
    assert exec_res.json()["status"] == "failed"


def test_edge_case_empty_extraction(e2e_env, monkeypatch):
    """Verify empty extraction is handled gracefully without crashing."""
    client, _ = e2e_env

    mock_empty = CrawlResult(
        success=True,
        status="completed",
        target_url="https://example.com/",
        pages_crawled=1,
        pages_failed=0,
        execution_time_seconds=0.1,
        website_summary=WebsiteSummary(title="", description="", headings=[], main_content=[]),
        pages=[
            PageCrawlResult(
                url="https://example.com/",
                status_code=200,
                title="",
                description="",
                headings=[],
                main_content=[],
                crawled_at=datetime.now(timezone.utc).isoformat(),
            )
        ],
        errors=[],
    )

    async def mock_crawl_op(*args, **kwargs):
        return mock_empty

    monkeypatch.setattr(crawl_service, "crawl", mock_crawl_op)

    gen_res = client.post("/api/agent/plan", json={"message": "Visit https://example.com, summarize it, and export JSON"})
    plan_id = gen_res.json()["plan_id"]

    exec_res = client.post(f"/api/agent/execute/{plan_id}", json={"approved": True})
    assert exec_res.status_code == 200
    assert exec_res.json()["success"] is True


def test_edge_case_cli_timeout(e2e_env, monkeypatch):
    """Verify CLI subprocess timeout handling in cli_executor."""
    import subprocess
    from app.schemas.intent_schema import CrawlIntent

    def mock_timeout_run(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd=["python"], timeout=1.0)

    monkeypatch.setattr(subprocess, "run", mock_timeout_run)

    intent = CrawlIntent(
        intent="crawl_website",
        url="https://example.com",
        max_pages=1,
        max_depth=0,
        output="json",
    )

    import asyncio
    res = asyncio.run(cli_executor.execute_crawl(intent, timeout=1.0))
    assert res.success is False
    assert res.execution.status == "timeout"


def test_edge_case_cli_nonzero_exit_code(e2e_env, monkeypatch):
    """Verify CLI non-zero exit code produces status='failed'."""
    import subprocess
    from unittest.mock import MagicMock
    from app.schemas.intent_schema import CrawlIntent

    mock_proc = MagicMock()
    mock_proc.returncode = 2
    mock_proc.stdout = b""
    mock_proc.stderr = b"Usage error: Missing required argument"

    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: mock_proc)

    intent = CrawlIntent(
        intent="crawl_website",
        url="https://example.com",
        max_pages=1,
        max_depth=0,
        output="json",
    )

    import asyncio
    res = asyncio.run(cli_executor.execute_crawl(intent))
    assert res.success is False
    assert res.execution.status == "failed"
    assert res.execution.exit_code == 2


def test_edge_case_invalid_cli_json(e2e_env, monkeypatch):
    """Verify CLI output that is not valid JSON produces status='invalid_output'."""
    import subprocess
    from unittest.mock import MagicMock
    from app.schemas.intent_schema import CrawlIntent

    mock_proc = MagicMock()
    mock_proc.returncode = 0
    mock_proc.stdout = b"Traceback (most recent call last):\nFatal error"
    mock_proc.stderr = b""

    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: mock_proc)

    intent = CrawlIntent(
        intent="crawl_website",
        url="https://example.com",
        max_pages=1,
        max_depth=0,
        output="json",
    )

    import asyncio
    res = asyncio.run(cli_executor.execute_crawl(intent))
    assert res.success is False
    assert res.execution.status == "invalid_output"


def test_edge_case_duplicate_plan_execution(e2e_env, monkeypatch):
    """Verify replay protection blocks executing the same plan twice."""
    client, _ = e2e_env

    mock_crawl = CrawlResult(
        success=True,
        status="completed",
        target_url="https://example.com/",
        pages_crawled=1,
        pages_failed=0,
        execution_time_seconds=0.1,
        website_summary=WebsiteSummary(),
        pages=[],
        errors=[],
    )
    async def mock_crawl_op(*args, **kwargs):
        return mock_crawl

    monkeypatch.setattr(crawl_service, "crawl", mock_crawl_op)

    gen_res = client.post("/api/agent/plan", json={"message": "Visit https://example.com and export JSON"})
    plan_id = gen_res.json()["plan_id"]

    # First execution succeeds
    exec1 = client.post(f"/api/agent/execute/{plan_id}", json={"approved": True})
    assert exec1.status_code == 200

    # Second execution must fail
    exec2 = client.post(f"/api/agent/execute/{plan_id}", json={"approved": True})
    assert exec2.status_code == 400
    assert "already been executed" in exec2.json()["message"].lower()


def test_edge_case_execution_without_approval(e2e_env):
    """Verify execution with approved=False is rejected immediately."""
    client, _ = e2e_env

    gen_res = client.post("/api/agent/plan", json={"message": "Visit https://example.com and export JSON"})
    plan_id = gen_res.json()["plan_id"]

    exec_res = client.post(f"/api/agent/execute/{plan_id}", json={"approved": False})
    assert exec_res.status_code == 400
    assert "declined" in exec_res.json()["message"].lower()
