"""Deterministic formatting for straightforward due-date questions in AI chat."""
from __future__ import annotations

import ast
import json
import re
from datetime import datetime, timezone
from typing import Any, Iterable

from sqlalchemy.orm import Session

from app import models
from app.date_utils import APP_TIMEZONE, format_stored_due_date_local


_DUE_DATE_QUESTION = re.compile(
    r"\b(?:when\b.*\b(?:due|deadline)\b|"
    r"what(?:'s| is)\s+(?:the\s+)?(?:due\s+date|deadline)\b)",
    re.IGNORECASE,
)


def _title_mentioned(title: str, text: str) -> bool:
    return bool(title and title.casefold() in text.casefold())


def _decode_tool_content(content: Any) -> Any:
    """Decode common LangChain tool-result representations without executing code."""
    if not isinstance(content, str):
        return content
    try:
        return json.loads(content)
    except (json.JSONDecodeError, TypeError):
        try:
            return ast.literal_eval(content)
        except (ValueError, SyntaxError):
            return None


def _task_records(value: Any) -> Iterable[dict[str, Any]]:
    """Find task-like records recursively in a tool result."""
    if isinstance(value, dict):
        if "title" in value and ("due_date" in value or "due_date_local" in value):
            yield value
        for nested in value.values():
            if isinstance(nested, (dict, list, tuple)):
                yield from _task_records(nested)
    elif isinstance(value, (list, tuple)):
        for nested in value:
            yield from _task_records(nested)


def _answer_for_record(record: dict[str, Any]) -> str:
    title = str(record.get("title") or "This task")
    due_date = record.get("due_date")
    if due_date is None:
        return f'Your task "{title}" does not have a due date set.'

    try:
        if isinstance(due_date, datetime):
            stored_value = due_date
        else:
            raw = str(due_date).strip()
            if raw.endswith("Z"):
                raw = raw[:-1] + "+00:00"
            stored_value = datetime.fromisoformat(raw)
        if stored_value.tzinfo is None:
            stored_value = stored_value.replace(tzinfo=timezone.utc)
        else:
            stored_value = stored_value.astimezone(timezone.utc)
        local_value = stored_value.astimezone(APP_TIMEZONE)
    except (TypeError, ValueError):
        # Tool output already has an application-local display field. Use it
        # only when we cannot safely format the UTC field ourselves.
        local_display = record.get("due_date_local")
        if local_display:
            return f'Your task "{title}" is due on {local_display}.'
        return f'I found the due date for "{title}", but could not format it reliably.'

    if (
        local_value.hour,
        local_value.minute,
        local_value.second,
        local_value.microsecond,
    ) == (0, 0, 0, 0):
        display_date = local_value.strftime("%B %d, %Y")
        return f'Your task "{title}" is due on {display_date}.'

    local_display = format_stored_due_date_local(stored_value)
    return f'Your task "{title}" is due on {local_display}.'


def answer_due_date_question(
    message: str,
    db: Session,
    user_id: int,
    conversation_messages: list[Any] | None = None,
) -> str | None:
    """Answer direct due-date questions from trusted task records.

    For ambiguous cases return None so the normal LangGraph response is used.
    Only the authenticated user's personal tasks are queried as a fallback.
    """
    if not message or not _DUE_DATE_QUESTION.search(message):
        return None

    quoted = re.search(r"""["']([^"']{1,200})["']""", message)
    quoted_title = quoted.group(1).strip() if quoted else None

    # Prefer task records returned by tools in this turn. That also supports
    # follow-ups such as "when is this due after the update?" where the title
    # is established by the conversation rather than repeated in the message.
    messages = conversation_messages or []
    last_human_index = max(
        (i for i, item in enumerate(messages) if getattr(item, "type", None) == "human"),
        default=-1,
    )
    records: list[dict[str, Any]] = []
    for item in messages[last_human_index + 1 :]:
        if getattr(item, "type", None) != "tool":
            continue
        records.extend(_task_records(_decode_tool_content(getattr(item, "content", None))))

    # Deduplicate records from retries/parallel tool calls by title + deadline.
    unique_records: dict[tuple[str, str], dict[str, Any]] = {}
    for record in records:
        key = (str(record.get("title") or ""), str(record.get("due_date")))
        unique_records[key] = record
    records = list(unique_records.values())

    selected: dict[str, Any] | None = None
    if quoted_title:
        selected = next(
            (record for record in records if str(record.get("title", "")).casefold() == quoted_title.casefold()),
            None,
        )
    if selected is None:
        # Match candidates against the current request, then the most recent
        # conversation context. Do not pick arbitrarily when multiple tasks fit.
        selected = next(
            (record for record in records if _title_mentioned(str(record.get("title", "")), message)),
            None,
        )
    refers_to_context = bool(
        re.search(r"\\b(this|that|it|the task|my task)\\b", message, re.IGNORECASE)
    )
    if selected is None and records and refers_to_context:
        for item in reversed(messages[:last_human_index]):
            text = getattr(item, "content", "")
            if not isinstance(text, str):
                continue
            matches = [
                record for record in records
                if _title_mentioned(str(record.get("title", "")), text)
            ]
            if len(matches) == 1:
                selected = matches[0]
                break
    if selected is None and len(records) == 1 and refers_to_context:
        selected = records[0]

    if selected is not None:
        return _answer_for_record(selected)

    # Directly quoted task-title fallback handles simple questions even when
    # the agent did not call a retrieval tool during this turn.
    if not quoted_title:
        return None
    task = (
        db.query(models.tasks)
        .filter(
            models.tasks.users_id == user_id,
            models.tasks.title.ilike(quoted_title),
        )
        .first()
    )
    if task is None:
        return None
    return _answer_for_record(
        {
            "title": task.title,
            "due_date": task.due_date,
            "due_date_local": format_stored_due_date_local(task.due_date),
        }
    )
