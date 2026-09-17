import os
import tempfile

os.environ.setdefault("DATABASE_URL", f"sqlite:///{tempfile.gettempdir()}/test_research.db")

from app.models.enums import Priority, ResearchStatus, TaskStatus
from app.models.research import ResearchJob, ResearchTask
from app.storage import repositories as repo


def test_save_and_get_job_roundtrip():
    job = ResearchJob(research_id="research_test1", question="Test question?", status=ResearchStatus.CREATED)
    repo.save_job(job)

    fetched = repo.get_job("research_test1")

    assert fetched is not None
    assert fetched.question == "Test question?"
    assert fetched.status == ResearchStatus.CREATED


def test_save_and_get_task_roundtrip():
    task = ResearchTask(
        task_id="task_test1", research_id="research_test1", question="Sub-question?",
        priority=Priority.HIGH, search_queries=["q1", "q2"], status=TaskStatus.PENDING,
    )
    repo.save_task(task)

    tasks = repo.get_tasks("research_test1")

    assert any(t.task_id == "task_test1" for t in tasks)
    match = next(t for t in tasks if t.task_id == "task_test1")
    assert match.search_queries == ["q1", "q2"]
    assert match.priority == Priority.HIGH
