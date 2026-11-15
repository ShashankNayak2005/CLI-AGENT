"""
Integration tests for Task History API and Chat Persistence.
Uses an isolated temporary SQLite database file to verify persistence and restarts.
"""

import json
from pathlib import Path
import tempfile
from unittest.mock import AsyncMock, patch
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.models.database import Base, get_db
from app.models.task import TaskModel
from app.schemas.crawl_schema import CrawlResult, WebsiteSummary
from app.schemas.intent_schema import CrawlIntent, IntentValidationResult
from app.services.cli_executor import CLIExecutorResult, ProcessExecutionDetails
from app.services.task_service import TaskService


@pytest.fixture
def temp_db_setup(tmp_path):
    """Sets up a temporary SQLite file database for integration testing."""
    db_file = tmp_path / "test_cli_agent.db"
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

    yield client, TestingSession, db_url, engine

    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)


def test_get_tasks_empty(temp_db_setup):
    client, _, _, _ = temp_db_setup
    response = client.get("/api/tasks")
    assert response.status_code == 200
    data = response.json()
    assert data["tasks"] == []
    assert data["total"] == 0


def test_get_task_details_and_not_found(temp_db_setup):
    client, SessionLocal, _, _ = temp_db_setup
    session = SessionLocal()
    task = TaskService.create_task(session, user_message="Check example.com")
    session.close()

    # Success retrieval
    res = client.get(f"/api/tasks/{task.id}")
    assert res.status_code == 200
    detail = res.json()
    assert detail["id"] == task.id
    assert detail["user_message"] == "Check example.com"

    # Missing ID
    missing_res = client.get("/api/tasks/missing_task_id_999")
    assert missing_res.status_code == 404


def test_delete_task_endpoint(temp_db_setup):
    client, SessionLocal, _, _ = temp_db_setup
    session = SessionLocal()
    task = TaskService.create_task(session, user_message="To be deleted")
    task_id = task.id
    session.close()

    del_res = client.delete(f"/api/tasks/{task_id}")
    assert del_res.status_code == 200
    del_data = del_res.json()
    assert del_data["success"] is True

    # Confirm it's gone
    assert client.get(f"/api/tasks/{task_id}").status_code == 404

    # Deleting again returns 404
    assert client.delete(f"/api/tasks/{task_id}").status_code == 404


def test_get_task_result_download(temp_db_setup):
    client, SessionLocal, _, _ = temp_db_setup
    session = SessionLocal()
    sample_crawl = {"pages_crawled": 1, "target_url": "https://example.com"}
    task = TaskService.create_task(session, user_message="Download test")
    TaskService.update_task_execution(
        session,
        task_id=task.id,
        status="completed",
        result_json=json.dumps(sample_crawl),
    )
    task_id = task.id
    session.close()

    res = client.get(f"/api/tasks/{task_id}/result")
    assert res.status_code == 200
    assert "attachment" in res.headers["content-disposition"]
    assert res.json() == sample_crawl


def test_chat_execution_persists_successful_crawl(temp_db_setup):
    client, SessionLocal, _, _ = temp_db_setup

    mock_intent = CrawlIntent(
        intent="crawl_website",
        url="https://example.com",
        max_pages=2,
        max_depth=1,
        output="json",
    )
    mock_intent_res = IntentValidationResult(is_supported=True, crawl_intent=mock_intent)

    mock_crawl_result = CrawlResult(
        success=True,
        status="completed",
        target_url="https://example.com/",
        pages_crawled=1,
        pages_failed=0,
        execution_time_seconds=0.75,
        website_summary=WebsiteSummary(title="Example Domain", description="Test"),
        pages=[],
        errors=[],
    )

    mock_exec_res = CLIExecutorResult(
        success=True,
        message="Crawl completed",
        execution=ProcessExecutionDetails(
            status="completed",
            exit_code=0,
            duration_seconds=0.75,
            stdout='{"mock": "stdout"}',
            stderr="[INFO] Finished",
        ),
        parsed_crawl_result=mock_crawl_result,
    )

    with patch("app.api.chat.groq_service.understand_intent", new_callable=AsyncMock) as mock_groq, \
         patch("app.api.chat.cli_executor.execute_crawl", new_callable=AsyncMock) as mock_exec:
        mock_groq.return_value = mock_intent_res
        mock_exec.return_value = mock_exec_res

        chat_res = client.post(
            "/api/chat",
            json={"message": "Crawl https://example.com and summarize it"},
        )

        assert chat_res.status_code == 200
        data = chat_res.json()
        assert "task_id" in data
        task_id = data["task_id"]

        # Verify task is recorded in SQLite
        task_res = client.get(f"/api/tasks/{task_id}")
        assert task_res.status_code == 200
        saved_task = task_res.json()
        assert saved_task["status"] == "completed"
        assert saved_task["exit_code"] == 0
        assert saved_task["execution_duration"] == 0.75
        assert saved_task["parsed_result"]["target_url"] == "https://example.com/"


def test_task_history_persists_after_restart(temp_db_setup):
    client, SessionLocal, db_url, engine = temp_db_setup

    # Insert a task
    session1 = SessionLocal()
    task = TaskService.create_task(session1, user_message="Persistence test")
    task_id = task.id
    session1.close()

    # Simulate server restart by creating a brand-new engine on the same SQLite file
    engine.dispose()
    restart_engine = create_engine(db_url, connect_args={"check_same_thread": False})
    RestartSession = sessionmaker(autocommit=False, autoflush=False, bind=restart_engine)

    def restart_get_db():
        s = RestartSession()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_db] = restart_get_db
    new_client = TestClient(app)

    # Verify task still exists and can be retrieved
    res = new_client.get(f"/api/tasks/{task_id}")
    assert res.status_code == 200
    assert res.json()["user_message"] == "Persistence test"
