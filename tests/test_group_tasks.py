import pytest
from app import models


@pytest.fixture
def group_with_members(auth_client_user1, auth_client_user2, user1, user2):
    """Creates a group owned by user1, with user2 as a member."""
    group_res = auth_client_user1.post("/groups/", json={"name": "Sprint Team", "description": "Sprint tasks"})
    group_id = group_res.json()["id"]

    inv = auth_client_user1.post(f"/groups/{group_id}/invite", json={"email": user2.email})
    auth_client_user2.get(f"/groups/invitations/{inv.json()['token']}/accept")

    return group_id


def test_create_group_task_and_permissions(auth_client_user1, auth_client_user2, auth_client_user3, user1, user2, user3, group_with_members):
    """Only group owner can create tasks and can only assign to members."""
    group_id = group_with_members

    # 1. Non-owner member tries to create task -> 403
    member_create = auth_client_user2.post(f"/groups/{group_id}/tasks", json={
        "title": "Member Task",
        "description": "Should fail",
        "assigned_to": user2.id
    })
    assert member_create.status_code == 403
    assert member_create.json()["detail"] == "Only the group owner can create tasks."

    # 2. Owner assigns to non-member user3 -> 400
    invalid_assign = auth_client_user1.post(f"/groups/{group_id}/tasks", json={
        "title": "Task 1",
        "description": "Assigned to outsider",
        "assigned_to": user3.id
    })
    assert invalid_assign.status_code == 400
    assert invalid_assign.json()["detail"] == "User is not the member of this group"

    # 3. Owner creates task assigned to user2 -> 201
    valid_create = auth_client_user1.post(f"/groups/{group_id}/tasks", json={
        "title": "Backend API",
        "description": "Implement auth and tasks",
        "assigned_to": user2.id,
        "priority": "high"
    })
    assert valid_create.status_code == 201
    task_data = valid_create.json()
    assert task_data["title"] == "Backend API"
    assert task_data["assigned_to"] == user2.id
    assert task_data["group_id"] == group_id


def test_view_group_tasks_permissions(auth_client_user1, auth_client_user2, auth_client_user3, user1, user2, group_with_members):
    """Owner sees all tasks, member sees only assigned tasks, outsider gets 403."""
    group_id = group_with_members

    # Create task assigned to user1 (owner)
    auth_client_user1.post(f"/groups/{group_id}/tasks", json={
        "title": "Owner Task",
        "description": "For owner",
        "assigned_to": user1.id
    })

    # Create task assigned to user2 (member)
    t2_res = auth_client_user1.post(f"/groups/{group_id}/tasks", json={
        "title": "User2 Task",
        "description": "For user2",
        "assigned_to": user2.id
    })
    t2_id = t2_res.json()["id"]

    # Owner views all tasks in group -> sees 2 tasks
    owner_view = auth_client_user1.get(f"/groups/{group_id}/tasks")
    assert owner_view.status_code == 200
    assert len(owner_view.json()) == 2

    # Member views tasks in group -> sees only 1 task (assigned to user2)
    member_view = auth_client_user2.get(f"/groups/{group_id}/tasks")
    assert member_view.status_code == 200
    tasks = member_view.json()
    assert len(tasks) == 1
    assert tasks[0]["id"] == t2_id

    # Non-member views group tasks -> 403
    outsider_view = auth_client_user3.get(f"/groups/{group_id}/tasks")
    assert outsider_view.status_code == 403


def test_update_and_delete_group_task(auth_client_user1, auth_client_user2, user1, user2, group_with_members):
    """Owner can reassign; assignee can update status but cannot reassign; only owner can delete."""
    group_id = group_with_members

    create_res = auth_client_user1.post(f"/groups/{group_id}/tasks", json={
        "title": "Deploy Service",
        "description": "Setup Docker",
        "assigned_to": user2.id
    })
    task_id = create_res.json()["id"]

    # Assignee updates task title and completion status -> 200
    assignee_update = auth_client_user2.patch(f"/groups/{group_id}/tasks/{task_id}", json={
        "completed": True,
        "description": "Docker containerized"
    })
    assert assignee_update.status_code == 200
    assert assignee_update.json()["completed"] is True

    # Assignee tries to reassign task to user1 -> 403
    reassign_attempt = auth_client_user2.patch(f"/groups/{group_id}/tasks/{task_id}", json={
        "assigned_to": user1.id
    })
    assert reassign_attempt.status_code == 403
    assert reassign_attempt.json()["detail"] == "Members cannot reassign tasks"

    # Member tries to delete group task -> 403
    member_del = auth_client_user2.delete(f"/groups/{group_id}/tasks/{task_id}")
    assert member_del.status_code == 403
    assert member_del.json()["detail"] == "Only the group owner can delete tasks"

    # Owner deletes group task -> 200
    owner_del = auth_client_user1.delete(f"/groups/{group_id}/tasks/{task_id}")
    assert owner_del.status_code == 200
    assert owner_del.json()["message"] == "Task deleted successfully"


def test_get_single_group_task_authorization(auth_client_user1, auth_client_user2, auth_client_user3, user1, user2, user3, group_with_members):
    """Owner and assignee can view single task; non-assigned member and non-member receive 403."""
    group_id = group_with_members

    create_res = auth_client_user1.post(f"/groups/{group_id}/tasks", json={
        "title": "Confidential Task",
        "description": "Assigned to user1",
        "assigned_to": user1.id
    })
    task_id = create_res.json()["id"]

    # 1. Owner can view -> 200
    owner_res = auth_client_user1.get(f"/groups/{group_id}/tasks/{task_id}")
    assert owner_res.status_code == 200
    assert owner_res.json()["id"] == task_id

    # 2. Member who is not assigned cannot view -> 403
    unassigned_res = auth_client_user2.get(f"/groups/{group_id}/tasks/{task_id}")
    assert unassigned_res.status_code == 403
    assert unassigned_res.json()["detail"] == "You are not authorized to view this task"

    # 3. Non-member cannot view -> 403
    outsider_res = auth_client_user3.get(f"/groups/{group_id}/tasks/{task_id}")
    assert outsider_res.status_code == 403



def test_group_subtasks_lifecycle_and_authorization(auth_client_user1, auth_client_user2, auth_client_user3, user1, user2, group_with_members, db):
    """Test group subtask CRUD, authorization, and cascade deletion."""
    group_id = group_with_members

    # Owner creates task assigned to user2
    task_res = auth_client_user1.post(f"/groups/{group_id}/tasks", json={
        "title": "Build UI",
        "description": "Frontend screens",
        "assigned_to": user2.id
    })
    task_id = task_res.json()["id"]

    # 1. Non-member user3 tries to add subtask -> 403
    unauth_sub = auth_client_user3.post(f"/groups/{group_id}/tasks/{task_id}/subtasks", json={"title": "Hacked subtask"})
    assert unauth_sub.status_code == 403

    # 2. Assignee (user2) creates group subtask -> 201
    sub_res = auth_client_user2.post(f"/groups/{group_id}/tasks/{task_id}/subtasks", json={
        "title": "Build Navbar",
        "description": "Navigation links"
    })
    assert sub_res.status_code == 201
    sub_data = sub_res.json()
    assert sub_data["title"] == "Build Navbar"
    assert sub_data["group_task_id"] == task_id
    subtask_id = sub_data["id"]

    # 3. View group subtasks (assignee and owner can view)
    view_sub_assignee = auth_client_user2.get(f"/groups/{group_id}/tasks/{task_id}/subtasks")
    assert view_sub_assignee.status_code == 200
    assert len(view_sub_assignee.json()) == 1

    view_sub_owner = auth_client_user1.get(f"/groups/{group_id}/tasks/{task_id}/subtasks")
    assert view_sub_owner.status_code == 200
    assert len(view_sub_owner.json()) == 1

    # 4. Update group subtask
    update_res = auth_client_user2.patch(f"/groups/{group_id}/tasks/subtasks/{subtask_id}", json={
        "completed": True,
        "title": "Navbar Complete"
    })
    assert update_res.status_code == 200
    assert update_res.json()["completed"] is True
    assert update_res.json()["title"] == "Navbar Complete"

    # 5. Delete group task cascades to subtask
    del_task_res = auth_client_user1.delete(f"/groups/{group_id}/tasks/{task_id}")
    assert del_task_res.status_code == 200

    # Verify subtask is gone in DB
    sub_in_db = db.query(models.GroupSubtask).filter(models.GroupSubtask.id == subtask_id).first()
    assert sub_in_db is None
