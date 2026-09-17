from app.models.enums import Priority
from app.models.research import PlanTask, ResearchPlan


def test_research_plan_validates_tasks():
    plan = ResearchPlan(
        title="Test",
        objective="Test objective",
        tasks=[
            PlanTask(id="task_1", question="What is X?", priority=Priority.HIGH, search_queries=["x"]),
        ],
    )
    assert len(plan.tasks) == 1
    assert plan.tasks[0].priority == Priority.HIGH


def test_plan_task_defaults_to_medium_priority():
    task = PlanTask(id="task_2", question="What is Y?")
    assert task.priority == Priority.MEDIUM
    assert task.search_queries == []
