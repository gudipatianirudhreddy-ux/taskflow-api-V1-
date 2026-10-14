import json
from types import SimpleNamespace

from app.services.due_date_response import answer_due_date_question


def message(kind: str, content: str):
    return SimpleNamespace(type=kind, content=content)


def test_due_date_question_uses_local_calendar_date_from_tool_result():
    messages = [
        message("human", 'When is the due date for "Prepare my resume for internships"?'),
        message(
            "tool",
            json.dumps({
                "id": 12,
                "title": "Prepare my resume for internships",
                "due_date": "2026-10-19T18:30:00Z",
                "due_date_local": "October 20, 2026 at 12:00 AM IST (Asia/Kolkata)",
            }),
        ),
    ]

    answer = answer_due_date_question(messages[0].content, None, 7, messages)

    assert answer == 'Your task "Prepare my resume for internships" is due on October 20, 2026.'
    assert "UTC" not in answer
    assert "18:30" not in answer


def test_follow_up_uses_task_referenced_in_recent_conversation_context():
    messages = [
        message("human", 'Move "Prepare my resume for internships" to tomorrow.'),
        message("ai", "Done — I updated the deadline for Prepare my resume for internships."),
        message("human", "When is this due after updating?"),
        message(
            "tool",
            json.dumps({
                "id": 12,
                "title": "Prepare my resume for internships",
                "due_date": "2026-10-14T18:30:00Z",
                "due_date_local": "October 15, 2026 at 12:00 AM IST (Asia/Kolkata)",
            }),
        ),
    ]

    answer = answer_due_date_question(messages[2].content, None, 7, messages)

    assert answer == 'Your task "Prepare my resume for internships" is due on October 15, 2026.'


def test_due_date_question_does_not_arbitrarily_choose_between_tasks():
    messages = [
        message("human", "When are my tasks due?"),
        message(
            "tool",
            json.dumps([
                {
                    "id": 1,
                    "title": "Prepare resume",
                    "due_date": "2026-10-19T18:30:00Z",
                    "due_date_local": "October 20, 2026 at 12:00 AM IST (Asia/Kolkata)",
                },
                {
                    "id": 2,
                    "title": "Finish project",
                    "due_date": "2026-10-20T18:30:00Z",
                    "due_date_local": "October 21, 2026 at 12:00 AM IST (Asia/Kolkata)",
                },
            ]),
        ),
    ]

    answer = answer_due_date_question(messages[0].content, None, 7, messages)

    assert answer is None


def test_non_due_date_question_uses_normal_agent_response():
    assert answer_due_date_question("Show all my tasks", None, 7, []) is None
