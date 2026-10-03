
from datetime import datetime

from app.services.task_planner import build_task_plan


def test_priority_and_due_date_order():
    tasks = [
        {
            "id": 1,
            "title": "Medium task",
            "priority": "MEDIUM",
            "due_date": "2026-10-03T12:00:00",
            "completed": False,
        },
        {
            "id": 2,
            "title": "Urgent later",
            "priority": "URGENT",
            "due_date": "2026-10-05T12:00:00",
            "completed": False,
        },
        {
            "id": 3,
            "title": "Urgent sooner",
            "priority": "URGENT",
            "due_date": "2026-10-03T12:00:00",
            "completed": False,
        },
    ]

    result = build_task_plan(
        tasks,
        now=datetime(2026, 10, 2, 12, 0),
    )

    ids = [task["id"] for task in result["recommendations"]]
    assert ids == [3, 2, 1]


def test_completed_tasks_are_excluded():
    tasks = [
        {
            "id": 1,
            "title": "Finished",
            "priority": "URGENT",
            "due_date": None,
            "completed": True,
        },
        {
            "id": 2,
            "title": "Pending",
            "priority": "LOW",
            "due_date": None,
            "completed": False,
        },
    ]

    result = build_task_plan(tasks)

    assert result["total_pending"] == 1
    assert result["recommendations"][0]["id"] == 2


def test_overdue_task_is_flagged():
    tasks = [
        {
            "id": 1,
            "title": "Late task",
            "priority": "HIGH",
            "due_date": "2026-10-01T12:00:00",
            "completed": False,
        },
    ]

    result = build_task_plan(
        tasks,
        now=datetime(2026, 10, 2, 12, 0),
    )

    task = result["recommendations"][0]
    assert task["overdue"] is True
    assert "overdue" in task["reason"].lower()


def test_tasks_without_deadlines_come_last_within_priority():
    tasks = [
        {
            "id": 1,
            "title": "No deadline",
            "priority": "HIGH",
            "due_date": None,
            "completed": False,
        },
        {
            "id": 2,
            "title": "Has deadline",
            "priority": "HIGH",
            "due_date": "2026-10-04T12:00:00",
            "completed": False,
        },
    ]

    result = build_task_plan(
        tasks,
        now=datetime(2026, 10, 2, 12, 0),
    )

    ids = [task["id"] for task in result["recommendations"]]
    assert ids == [2, 1]
