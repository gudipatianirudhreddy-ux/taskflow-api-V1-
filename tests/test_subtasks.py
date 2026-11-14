import pytest
from app import models


def test_zero_subtasks_returns_empty_list(auth_client_user1):
    """Loading a task with zero subtasks returns 200 and an empty list []."""
    task_res = auth_client_user1.post("/tasks/", json={"title": "Empty Task", "content": "No subtasks yet"})
    assert task_res.status_code == 200
    task_id = task_res.json()["id"]

    get_res = auth_client_user1.get(f"/tasks/{task_id}/subtasks")
    assert get_res.status_code == 200
    assert get_res.json() == []


def test_creating_first_subtask(auth_client_user1):
    """Creating the first subtask on a task with 0 subtasks succeeds with 201."""
    task_res = auth_client_user1.post("/tasks/", json={"title": "Parent Task", "content": "Description"})
    assert task_res.status_code == 200
    task_id = task_res.json()["id"]

    # Verify initially 0 subtasks
    assert auth_client_user1.get(f"/tasks/{task_id}/subtasks").json() == []

    # Create the first subtask
    sub_res = auth_client_user1.post(f"/tasks/{task_id}/subtasks", json={"title": "First Subtask"})
    assert sub_res.status_code == 201
    data = sub_res.json()
    assert data["title"] == "First Subtask"
    assert data["task_id"] == task_id
    assert data["completed"] is False

    # Verify list now has 1 subtask
    subs = auth_client_user1.get(f"/tasks/{task_id}/subtasks").json()
    assert len(subs) == 1
    assert subs[0]["id"] == data["id"]


def test_fetching_multiple_subtasks(auth_client_user1):
    """Fetching subtasks returns all created subtasks in order."""
    task_res = auth_client_user1.post("/tasks/", json={"title": "Multi-subtask Project", "content": "Several steps"})
    task_id = task_res.json()["id"]

    sub1 = auth_client_user1.post(f"/tasks/{task_id}/subtasks", json={"title": "Step 1"}).json()
    sub2 = auth_client_user1.post(f"/tasks/{task_id}/subtasks", json={"title": "Step 2"}).json()
    sub3 = auth_client_user1.post(f"/tasks/{task_id}/subtasks", json={"title": "Step 3"}).json()

    get_res = auth_client_user1.get(f"/tasks/{task_id}/subtasks")
    assert get_res.status_code == 200
    subs = get_res.json()
    assert len(subs) == 3
    sub_ids = [s["id"] for s in subs]
    assert sub1["id"] in sub_ids
    assert sub2["id"] in sub_ids
    assert sub3["id"] in sub_ids


def test_partial_update_completion_status(auth_client_user1):
    """PUT /tasks/subtasks/{subtask_id} supports partial updates (e.g. only completed)."""
    task_res = auth_client_user1.post("/tasks/", json={"title": "Task", "content": "Content"})
    task_id = task_res.json()["id"]

    create_res = auth_client_user1.post(f"/tasks/{task_id}/subtasks", json={"title": "Toggle Me", "content": "Original content"})
    subtask_id = create_res.json()["id"]
    assert create_res.json()["completed"] is False

    # Partial update: only toggle completed to True without providing title or content
    update_res = auth_client_user1.put(f"/tasks/subtasks/{subtask_id}", json={"completed": True})
    assert update_res.status_code == 200
    updated_data = update_res.json()
    assert updated_data["completed"] is True
    assert updated_data["title"] == "Toggle Me"  # Title preserved
    assert updated_data["content"] == "Original content"  # Content preserved

    # Partial update: update title only
    title_res = auth_client_user1.put(f"/tasks/subtasks/{subtask_id}", json={"title": "Renamed Subtask"})
    assert title_res.status_code == 200
    assert title_res.json()["title"] == "Renamed Subtask"
    assert title_res.json()["completed"] is True  # Completed preserved


def test_deleting_subtask(auth_client_user1):
    """Deleting a subtask removes it from the list while preserving other subtasks."""
    task_res = auth_client_user1.post("/tasks/", json={"title": "Task", "content": "Content"})
    task_id = task_res.json()["id"]

    sub1 = auth_client_user1.post(f"/tasks/{task_id}/subtasks", json={"title": "Keep Me"}).json()
    sub2 = auth_client_user1.post(f"/tasks/{task_id}/subtasks", json={"title": "Delete Me"}).json()

    # Delete sub2
    del_res = auth_client_user1.delete(f"/tasks/subtasks/{sub2['id']}")
    assert del_res.status_code == 200
    assert del_res.json()["Message"] == "Deleted successfully"

    # Verify only sub1 remains
    remaining = auth_client_user1.get(f"/tasks/{task_id}/subtasks").json()
    assert len(remaining) == 1
    assert remaining[0]["id"] == sub1["id"]

    # Delete sub1 -> now 0 subtasks, should return [] (not 404)
    del_res2 = auth_client_user1.delete(f"/tasks/subtasks/{sub1['id']}")
    assert del_res2.status_code == 200

    empty_list_res = auth_client_user1.get(f"/tasks/{task_id}/subtasks")
    assert empty_list_res.status_code == 200
    assert empty_list_res.json() == []


def test_prevent_access_to_another_users_task_and_subtasks(auth_client_user1, auth_client_user2):
    """User 2 cannot view, create, update, or delete subtasks on User 1's task."""
    task_res = auth_client_user1.post("/tasks/", json={"title": "User1 Private Task", "content": "Private"})
    task_id = task_res.json()["id"]

    sub_res = auth_client_user1.post(f"/tasks/{task_id}/subtasks", json={"title": "User1 Subtask"})
    subtask_id = sub_res.json()["id"]

    # User 2 tries to GET subtasks for User 1's task -> 404
    unauth_get = auth_client_user2.get(f"/tasks/{task_id}/subtasks")
    assert unauth_get.status_code == 404
    assert unauth_get.json()["detail"] == "Task not found or you do not have permission to view subtasks."

    # User 2 tries to POST subtask to User 1's task -> 404
    unauth_create = auth_client_user2.post(f"/tasks/{task_id}/subtasks", json={"title": "Intruder Subtask"})
    assert unauth_create.status_code == 404
    assert unauth_create.json()["detail"] == "Task not found or you do not have permission to add subtasks."

    # User 2 tries to PUT User 1's subtask -> 404
    unauth_update = auth_client_user2.put(f"/tasks/subtasks/{subtask_id}", json={"completed": True})
    assert unauth_update.status_code == 404
    assert unauth_update.json()["detail"] == "Subtask not found or you do not have permission to update subtask."

    # User 2 tries to DELETE User 1's subtask -> 404
    unauth_delete = auth_client_user2.delete(f"/tasks/subtasks/{subtask_id}")
    assert unauth_delete.status_code == 404
    assert unauth_delete.json()["detail"] == "Subtask not found or you do not have permission to delete subtask."


def test_nonexistent_task_subtasks_returns_404(auth_client_user1):
    """GET /tasks/{task_id}/subtasks for a nonexistent task returns 404."""
    res = auth_client_user1.get("/tasks/999999/subtasks")
    assert res.status_code == 404
    assert res.json()["detail"] == "Task not found or you do not have permission to view subtasks."


def test_task_cascade_deletes_subtasks(auth_client_user1, db):
    """Deleting a parent task cascades and removes all of its subtasks."""
    task_res = auth_client_user1.post("/tasks/", json={"title": "Parent Task", "content": "Parent"})
    task_id = task_res.json()["id"]

    sub_res = auth_client_user1.post(f"/tasks/{task_id}/subtasks", json={"title": "Child Subtask"})
    subtask_id = sub_res.json()["id"]

    del_task_res = auth_client_user1.delete(f"/tasks/{task_id}")
    assert del_task_res.status_code == 201

    sub_in_db = db.query(models.subtasks).filter(models.subtasks.id == subtask_id).first()
    assert sub_in_db is None
