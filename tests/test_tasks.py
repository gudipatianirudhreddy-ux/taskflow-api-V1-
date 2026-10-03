import pytest


def test_create_task(auth_client_user1, user1):
    """User can create a personal task."""
    payload = {
        "title": "Buy groceries",
        "content": "Milk, eggs, coffee",
        "priority": "high",
        "completed": False,
        "due_date": "2026-10-15T18:00:00"
    }
    response = auth_client_user1.post("/tasks/", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == payload["title"]
    assert data["content"] == payload["content"]
    assert data["priority"] == "high"
    assert data["completed"] is False
    assert "id" in data


def test_get_tasks_list_only_returns_own_tasks(auth_client_user1, auth_client_user2):
    """GET /tasks/ only returns tasks owned by the requesting user."""
    # User 1 creates a task
    auth_client_user1.post("/tasks/", json={"title": "User1 Task", "content": "Details 1"})
    # User 2 creates a task
    auth_client_user2.post("/tasks/", json={"title": "User2 Task", "content": "Details 2"})

    # User 1 list
    res1 = auth_client_user1.get("/tasks/")
    assert res1.status_code == 200
    tasks1 = res1.json()
    assert len(tasks1) == 1
    assert tasks1[0]["title"] == "User1 Task"

    # User 2 list
    res2 = auth_client_user2.get("/tasks/")
    assert res2.status_code == 200
    tasks2 = res2.json()
    assert len(tasks2) == 1
    assert tasks2[0]["title"] == "User2 Task"


def test_get_single_task_and_authorization(auth_client_user1, auth_client_user2):
    """A user can view their own task, but another user receives 404."""
    create_res = auth_client_user1.post("/tasks/", json={"title": "Secret Task", "content": "Top secret"})
    task_id = create_res.json()["id"]

    # Owner views it
    res1 = auth_client_user1.get(f"/tasks/{task_id}")
    assert res1.status_code == 200
    assert res1.json()["id"] == task_id
    assert res1.json()["title"] == "Secret Task"

    # Other user cannot view it
    res2 = auth_client_user2.get(f"/tasks/{task_id}")
    assert res2.status_code == 404
    assert res2.json()["detail"] == "Invalid id"


def test_update_task_and_authorization(auth_client_user1, auth_client_user2):
    """A user can update their own task, but another user cannot."""
    create_res = auth_client_user1.post("/tasks/", json={"title": "Old Title", "content": "Old Content"})
    task_id = create_res.json()["id"]

    update_payload = {
        "title": "New Title",
        "content": "Updated Content",
        "completed": True,
        "priority": "urgent"
    }

    # Other user attempts to update -> 404
    unauth_res = auth_client_user2.put(f"/tasks/{task_id}", json=update_payload)
    assert unauth_res.status_code == 404
    assert unauth_res.json()["detail"] == "id do not exists or not found"

    # Owner updates -> 200
    owner_res = auth_client_user1.put(f"/tasks/{task_id}", json=update_payload)
    assert owner_res.status_code == 200
    assert owner_res.json()["title"] == "New Title"
    assert owner_res.json()["completed"] is True
    assert owner_res.json()["priority"] == "urgent"


def test_delete_task_and_authorization(auth_client_user1, auth_client_user2):
    """A user can delete their own task, but another user cannot."""
    create_res = auth_client_user1.post("/tasks/", json={"title": "To Delete", "content": "Content"})
    task_id = create_res.json()["id"]

    # Other user attempts to delete -> 404
    unauth_res = auth_client_user2.delete(f"/tasks/{task_id}")
    assert unauth_res.status_code == 404
    assert unauth_res.json()["detail"] == "Invalid id or id do not exist"

    # Owner deletes -> 201
    owner_res = auth_client_user1.delete(f"/tasks/{task_id}")
    assert owner_res.status_code == 201
    assert owner_res.json()["Message"] == "Deleted successfully"

    # Check it no longer exists
    get_res = auth_client_user1.get(f"/tasks/{task_id}")
    assert get_res.status_code == 404
