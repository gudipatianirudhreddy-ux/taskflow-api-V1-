"""Small deterministic helpers for direct due-date questions in chat."""
from __future__ import annotations

import re
from datetime import datetime

from sqlalchemy.orm import Session

from app import models
from app.date_utils import format_stored_due_date_local


_DUE_DATE_QUESTION = re.compile(
    r"\b(when\s+(?:is|does|will)\b.*\b(?:due|deadline)\b|"
    r"what(?:'s| is)\s+the\s+(?:due\s+date|deadline)\b|"
    r"when\s+is\s+the\s+due\s+date\b)",
    re.IGNORECASE,
)


def answer_due_date_question(
    message: str,
    db: Session,
    user_id: int,
) -> str | None:
    """Return a deterministic answer for an unambiguous task-title question.

    Return None for requests this helper cannot confidently handle, leaving the
    normal agent workflow unchanged. Only the authenticated user's tasks are
    queried.
    """
    if not message or not _DUE_DATE_QUESTION.search(message):
        return None

    # Common natural phrasing: ... for "Task title"? / ... for 'Task title'?
    quoted_title = re.search(r"""["']([^"']{1,200})["']""", message)
    if not quoted_title:
        return None

    title = quoted_title.group(1).strip()
    if not title:
        return None

    task = (
        db.query(models.tasks)
        .filter(
            models.tasks.users_id == user_id,
            models.tasks.title.ilike(title),
        )
        .first()
    )
    if task is None:
        # Avoid silently choosing a task when titles differ by punctuation or
        # partial matching; let the agent handle clarification/retrieval.
        return None

    if task.due_date is None:
        return f'Your task "{task.title}" does not have a due date set.'

    local_due_date = format_stored_due_date_local(task.due_date)
    if local_due_date is None:
        return f'Your task "{task.title}" does not have a due date set.'

    # For date-only deadlines, the local calendar date is the information users
    # generally need. Include time/timezone only when the stored deadline is not
    # midnight in the application timezone.
    local_value = task.due_date
    if local_value.tzinfo is None:
        from datetime import timezone
        local_value = local_value.replace(tzinfo=timezone.utc)
    else:
        from datetime import timezone
        local_value = local_value.astimezone(timezone.utc)
    from app.date_utils import APP_TIMEZONE
    local_value = local_value.astimezone(APP_TIMEZONE)

    if (local_value.hour, local_value.minute, local_value.second, local_value.microsecond) == (0, 0, 0, 0):
        display_date = local_value.strftime("%B %d, %Y")
        return f'Your task "{task.title}" is due on {display_date}.'

    return f'Your task "{task.title}" is due on {local_due_date}.'
