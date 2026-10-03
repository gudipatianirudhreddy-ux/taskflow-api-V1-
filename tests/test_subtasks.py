import pytest
from app import models


def test_personal_subtask_crud(auth_client_user1):
    """Full CRUD lifecycle for personal subtasks."""
    # 1. Create a task first
    task_res = auth_client_user1.post("/tasks/", json={"title": "Main Project", "content": "Project description"})
    assert task_res.status_code == 200
    task_id = task_res.json()["id"]

    # 2. Create subtask
    sub_payload = {
        "title": "Subtask 1",
        "content": "Step 1 details",
        "completed": False,
        "due_date": "2026-11-01T12:00:00"
    }
    create_sub_res = auth_client_user1.post(f"/tasks/{task_id}/subtasks", json=sub_payload)
    assert create_sub_res.status_code == 201
    sub_data = create_sub_res.json()
    assert sub_data["title"] == "Subtask 1"
    assert sub_data["task_id"] == task_id
    subtask_id = sub_data["id"]

    # 3. Get subtasks for the task
    get_res = auth_client_user1.get(f"/tasks/{task_id}/subtasks")
    assert get_res.status_code == 200
    subtasks_list = get_res.json()
    assert len(subtasks_list) == 1
    assert subtasks_list[0]["id"] == subtask_id

    # 4. Update subtask
    update_payload = {
        "title": "Subtask 1 Updated",
        "content": "Updated details",
        "completed": True
    }
    update_res = auth_client_user1.put(f"/tasks/subtasks/{subtask_id}", json=update_payload)
    assert update_res.status_code == 200
    assert update_res.json()["title"] == "Subtask 1 Updated"
    assert update_res.json()["completed"] is True

    # 5. Delete subtask
    del_res = auth_client_user1.delete(f"/tasks/subtasks/{subtask_id}")
    assert del_res.status_code == 200
    assert del_res.json()["Message"] == "Deleted successfully"

    # Confirm it's gone
    get_after_del = auth_client_user1.get(f"/tasks/{task_id}/subtasks")
    assert get_after_del.status_code == 404


def test_subtask_authorization_user_cannot_access_others(auth_client_user1, auth_client_user2):
    """User 2 cannot create, view, update, or delete subtasks on User 1's task."""
    # User 1 creates task and subtask
    task_res = auth_client_user1.post("/tasks/", json={"title": "User1 Task", "content": "Private"})
    task_id = task_res.json()["id"]

    sub_res = auth_client_user1.post(f"/tasks/{task_id}/subtasks", json={"title": "Private Subtask"})
    subtask_id = sub_res.json()["id"]

    # User 2 tries to create subtask on User 1's task -> 404
    unauth_create = auth_client_user2.post(f"/tasks/{task_id}/subtasks", json={"title": "Hacker Subtask"})
    assert unauth_create.status_code == 404
    assert unauth_create.json()["detail"] == "Task not found or you do not have permission to add subtasks."

    # User 2 tries to view User 1's subtasks -> 404
    unauth_view = auth_client_user2.get(f"/tasks/{task_id}/subtasks")
    assert unauth_view.status_code == 404
    assert unauth_view.json()["detail"] == "Subtasks not found or you do not have permission to view subtasks."

    # User 2 tries to update User 1's subtask -> 404
    unauth_update = auth_client_user2.put(f"/tasks/subtasks/{subtask_id}", json={"title": "Tampered"})
    assert unauth_update.status_code == 404
    assert unauth_update.json()["detail"] == "Subtask not found or you do not have permission to update subtask."

    # User 2 tries to delete User 1's subtask -> 404
    unauth_delete = auth_client_user2.delete(f"/tasks/subtasks/{subtask_id}")
    assert unauth_delete.status_code == 404
    assert unauth_delete.json()["detail"] == "Subtask not found or you do not have permission to delete subtask."


def test_task_cascade_deletes_subtasks(auth_client_user1, db):
    """Deleting a parent task cascades and removes all of its subtasks."""
    task_res = auth_client_user1.post("/tasks/", json={"title": "Parent Task", "content": "Parent"})
    task_id = task_res.json()["id"]

    sub_res = auth_client_user1.post(f"/tasks/{task_id}/subtasks", json={"title": "Child Subtask"})
    subtask_id = sub_res.json()["id"]

    # Delete parent task
    del_task_res = auth_client_user1.delete(f"/tasks/{task_id}")
    assert del_task_res.status_code == 201

    # Verify subtask is gone in database
    sub_in_db = db.query(models.subtasks).filter(models.subtasks.id == subtask_id).first()
    assert sub_in_db is None
