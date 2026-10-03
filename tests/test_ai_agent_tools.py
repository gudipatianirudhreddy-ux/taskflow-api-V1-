import pytest
from app import models
from app.services.ai_service import get_task_tools
from app.services.group_ai_service import get_group_tools


def test_personal_agent_tools_user_isolation(db, user1, user2):
    """Personal agent tools cannot read, update, or delete tasks belonging to other users."""
    tools_user1 = {t.name: t for t in get_task_tools(db, user1.id)}
    tools_user2 = {t.name: t for t in get_task_tools(db, user2.id)}

    # User 1 creates task via tool
    created = tools_user1["create_task"].invoke({
        "title": "User1 Confidential Task",
        "content": "Secret notes"
    })
    task_id = created["id"]

    # 1. User 2's get_tasks does not include User 1's task
    user2_tasks = tools_user2["get_tasks"].invoke({})
    assert all(t["id"] != task_id for t in user2_tasks)

    # 2. User 2's get_task returns error for User 1's task
    get_res = tools_user2["get_task"].invoke({"id": task_id})
    assert "error" in get_res
    assert get_res["error"] == "Task not found"

    # 3. User 2's update_tasks returns error and does not mutate task
    update_res = tools_user2["update_tasks"].invoke({
        "id": task_id,
        "title": "Hacked Title"
    })
    assert "error" in update_res
    assert update_res["error"] == "Task not found"

    # Verify task in DB was not altered
    task_in_db = db.query(models.tasks).filter(models.tasks.id == task_id).first()
    assert task_in_db.title == "User1 Confidential Task"

    # 4. User 2's delete_task returns error and does not remove task
    del_res = tools_user2["delete_task"].invoke({"id": task_id})
    assert "error" in del_res
    assert del_res["error"] == "Task not found"

    task_still_exists = db.query(models.tasks).filter(models.tasks.id == task_id).first()
    assert task_still_exists is not None


def test_group_agent_tools_authorization(db, user1, user2, user3):
    """Group agent tools enforce membership, ownership, and assignment boundaries."""
    tools_user1 = {t.name: t for t in get_group_tools(db, user1.id)}  # Owner
    tools_user2 = {t.name: t for t in get_group_tools(db, user2.id)}  # Member
    tools_user3 = {t.name: t for t in get_group_tools(db, user3.id)}  # Non-member

    # User 1 creates a group
    group_created = tools_user1["create_group"].invoke({
        "name": "AI Dev Group",
        "description": "LangGraph research"
    })
    group_id = group_created["id"]

    # Add user2 to the group as member
    member = models.Members(group_id=group_id, user_id=user2.id, role=models.Role.member.value)
    db.add(member)
    db.commit()

    # 1. Non-member (user3) cannot get group info or group members
    unauth_info = tools_user3["get_group_info"].invoke({"group_id": group_id})
    assert "error" in unauth_info
    assert unauth_info["error"] == "You are not a member of this group"

    unauth_members = tools_user3["get_group_members"].invoke({"group_id": group_id})
    assert "error" in unauth_members
    assert unauth_members["error"] == "You are not a member of this group"

    # 2. Non-owner member (user2) cannot create group tasks
    unauth_create_task = tools_user2["create_group_tasks"].invoke({
        "group_id": group_id,
        "title": "Illegal Task",
        "description": "Unauthorized",
        "assigned_to": user2.id
    })
    assert "error" in unauth_create_task
    assert unauth_create_task["error"] == "Only owner can create tasks"

    # 3. Owner cannot assign task to non-member (user3)
    invalid_assign = tools_user1["create_group_tasks"].invoke({
        "group_id": group_id,
        "title": "Task for outsider",
        "description": "Should fail",
        "assigned_to": user3.id
    })
    assert "error" in invalid_assign
    assert invalid_assign["error"] == "Assigned user is not a member of this group"

    # 4. Owner creates task assigned to user2
    task_created = tools_user1["create_group_tasks"].invoke({
        "group_id": group_id,
        "title": "Implement LangGraph Tools",
        "description": "Agent authorization tests",
        "assigned_to": user2.id
    })
    task_id = task_created["id"]

    # 5. Non-member cannot see group tasks
    unauth_tasks = tools_user3["get_group_tasks"].invoke({"group_id": group_id})
    assert "error" in unauth_tasks
    assert unauth_tasks["error"] == "Member does not exists in this group"

    # 6. Non-owner cannot update or delete group tasks
    unauth_update = tools_user2["update_group_task"].invoke({
        "group_id": group_id,
        "task_id": task_id,
        "title": "Member updated"
    })
    assert "error" in unauth_update
    assert unauth_update["error"] == "Only owner can update group tasks"

    unauth_delete = tools_user2["delete_group_task"].invoke({
        "group_id": group_id,
        "task_id": task_id
    })
    assert "error" in unauth_delete
    assert unauth_delete["error"] == "Only owner can delete group tasks"

    # 7. Non-owner cannot delete the group
    unauth_del_group = tools_user2["delete_group"].invoke({"group_id": group_id})
    assert "error" in unauth_del_group
    assert unauth_del_group["error"] == "Only owner can delete the group"

    # 8. User 2 checks get_my_group_tasks and sees the task
    my_tasks = tools_user2["get_my_group_tasks"].invoke({})
    assert len(my_tasks) == 1
    assert my_tasks[0]["task_id"] == task_id
