"""
Unit tests for SQLAlchemy Database Initialization and TaskService.
Uses an isolated in-memory SQLite database for test execution.
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.database import Base
from app.models.task import TaskModel
from app.services.task_service import TaskService


@pytest.fixture
def test_db():
    """Provides an isolated in-memory SQLite session for testing."""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSession()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


def test_database_initialization(test_db):
    """Verify tables are created and queryable."""
    tasks = test_db.query(TaskModel).all()
    assert tasks == []


def test_task_creation(test_db):
    """Verify task creation persists all baseline fields."""
    task = TaskService.create_task(
        db=test_db,
        user_message="Crawl https://example.com",
        intent="crawl_website",
        target_url="https://example.com/",
        status="running",
    )
    assert task.id is not None
    assert task.user_message == "Crawl https://example.com"
    assert task.intent == "crawl_website"
    assert task.target_url == "https://example.com/"
    assert task.status == "running"
    assert task.created_at is not None


def test_task_updates(test_db):
    """Verify updating execution status and output."""
    task = TaskService.create_task(
        db=test_db,
        user_message="Crawl https://example.com",
    )
    updated = TaskService.update_task_execution(
        db=test_db,
        task_id=task.id,
        status="completed",
        exit_code=0,
        stdout='{"success": true}',
        stderr="[INFO] Done",
        result_json='{"pages_crawled": 1}',
        execution_duration=1.25,
    )
    assert updated is not None
    assert updated.status == "completed"
    assert updated.exit_code == 0
    assert updated.execution_duration == 1.25
    assert updated.completed_at is not None
    assert updated.result_json == '{"pages_crawled": 1}'


def test_recent_tasks_and_pagination(test_db):
    """Verify pagination and newest-first ordering."""
    for i in range(15):
        TaskService.create_task(
            db=test_db,
            user_message=f"Prompt #{i}",
        )

    tasks_page1, total = TaskService.get_recent_tasks(test_db, limit=5, offset=0)
    assert total == 15
    assert len(tasks_page1) == 5
    # Newest prompt was created last
    assert tasks_page1[0].user_message == "Prompt #14"

    tasks_page2, _ = TaskService.get_recent_tasks(test_db, limit=5, offset=5)
    assert len(tasks_page2) == 5
    assert tasks_page2[0].user_message == "Prompt #9"


def test_task_deletion(test_db):
    """Verify task deletion."""
    task = TaskService.create_task(db=test_db, user_message="To delete")
    task_id = task.id

    assert TaskService.get_task_by_id(test_db, task_id) is not None
    deleted = TaskService.delete_task(test_db, task_id)
    assert deleted is True
    assert TaskService.get_task_by_id(test_db, task_id) is None


def test_missing_task_id(test_db):
    """Verify querying non-existent task IDs returns None / False."""
    assert TaskService.get_task_by_id(test_db, "non_existent_id") is None
    assert TaskService.delete_task(test_db, "non_existent_id") is False
    assert TaskService.update_task_execution(test_db, "non_existent_id", status="failed") is None
