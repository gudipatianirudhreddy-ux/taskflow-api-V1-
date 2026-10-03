
from datetime import datetime, timezone
from typing import Any


PRIORITY_ORDER = {
    "URGENT": 0,
    "HIGH": 1,
    "MEDIUM": 2,
    "LOW": 3,
}


def _normalize_priority(priority: Any) -> str:
    """Normalize a priority enum or string."""
    value = getattr(priority, "value", priority)
    return str(value).upper()


def _normalize_due_date(due_date: Any) -> datetime | None:
    """Accept datetime objects or ISO-formatted date strings."""
    if due_date is None:
        return None

    if isinstance(due_date, str):
        try:
            due_date = datetime.fromisoformat(
                due_date.replace("Z", "+00:00")
            )
        except ValueError:
            return None

    if not isinstance(due_date, datetime):
        return None

    # Normalize timezone-aware values for safe comparison.
    if due_date.tzinfo is not None:
        due_date = due_date.astimezone(timezone.utc).replace(
            tzinfo=None
        )

    return due_date


def build_task_plan(
    tasks: list[dict[str, Any]],
    now: datetime | None = None,
) -> dict[str, Any]:
    """
    Rank incomplete tasks by priority and due date.

    This function is read-only. It does not modify the database.
    """
    if now is None:
        now = datetime.now(timezone.utc)

    if now.tzinfo is not None:
        now = now.astimezone(timezone.utc).replace(tzinfo=None)

    pending_tasks = []

    for task in tasks:
        if task.get("completed", False):
            continue

        due_date = _normalize_due_date(task.get("due_date"))
        priority = _normalize_priority(
            task.get("priority", "MEDIUM")
        )

        overdue = due_date is not None and due_date < now

        pending_tasks.append({
            **task,
            "priority": priority,
            "due_date": due_date,
            "overdue": overdue,
        })

    # Priority first, then earliest deadline.
    # Tasks without deadlines come last within their priority.
    pending_tasks.sort(
        key=lambda task: (
            PRIORITY_ORDER.get(task["priority"], 99),
            task["due_date"] is None,
            task["due_date"] or datetime.max,
            task.get("id", 0),
        )
    )

    recommendations = []

    for index, task in enumerate(pending_tasks, start=1):
        priority = task["priority"]
        due_date = task["due_date"]
        overdue = task["overdue"]

        if overdue:
            reason = (
                "This task is overdue and should be reviewed promptly."
            )
        elif due_date is not None:
            reason = (
                f"It has {priority} priority and a deadline of "
                f"{due_date.isoformat(sep=' ', timespec='minutes')}."
            )
        else:
            reason = (
                f"It has {priority} priority but no deadline is set."
            )

        recommendations.append({
            "rank": index,
            "id": task.get("id"),
            "title": task.get("title", "Untitled task"),
            "priority": priority,
            "due_date": (
                due_date.isoformat(sep=" ", timespec="minutes")
                if due_date is not None
                else None
            ),
            "overdue": overdue,
            "reason": reason,
        })

    return {
        "total_pending": len(recommendations),
        "recommendations": recommendations,
    }
