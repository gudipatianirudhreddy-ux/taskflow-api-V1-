
import pytest
from app import models


def test_create_and_get_groups(auth_client_user1, user1):
    """Owner can create and retrieve groups."""
    res = auth_client_user1.post(
        "/groups/",
        json={"name": "Engineering", "description": "Core dev team"},
    )
    assert res.status_code == 201

    group_data = res.json()
    assert group_data["name"] == "Engineering"
    assert "id" in group_data

    # List groups as owner
    list_res = auth_client_user1.get("/groups/")
    assert list_res.status_code == 200

    groups = list_res.json()
    assert len(groups) == 1
    assert groups[0]["name"] == "Engineering"


def test_member_can_list_joined_group(
    auth_client_user1,
    auth_client_user2,
    user2,
):
    """A regular member can list a group they joined."""
    group_res = auth_client_user1.post(
        "/groups/",
        json={"name": "Project Beta", "description": "Beta"},
    )
    assert group_res.status_code == 201
    group_id = group_res.json()["id"]

    # Owner invites user2
    invite_res = auth_client_user1.post(
        f"/groups/{group_id}/invite",
        json={"email": user2.email},
    )
    assert invite_res.status_code == 201

    # User2 accepts the invitation
    accept_res = auth_client_user2.get(
        f"/groups/invitations/{invite_res.json()['token']}/accept"
    )
    assert accept_res.status_code == 202

    # User2 lists their groups
    list_res = auth_client_user2.get("/groups/")
    assert list_res.status_code == 200

    groups = list_res.json()
    assert any(group["id"] == group_id for group in groups)
    assert any(group["name"] == "Project Beta" for group in groups)


def test_authenticated_user_with_no_groups_gets_empty_list(
    auth_client_user3,
):
    """An authenticated user with no group memberships gets an empty list."""
    list_res = auth_client_user3.get("/groups/")

    assert list_res.status_code == 200
    assert list_res.json() == []


def test_group_authorization_non_owner(auth_client_user1, auth_client_user2):
    """Non-owner cannot view or patch another user's group directly."""
    create_res = auth_client_user1.post(
        "/groups/",
        json={"name": "Alpha", "description": "Alpha team"},
    )
    group_id = create_res.json()["id"]

    # User 2 tries to get group details -> 401
    unauth_get = auth_client_user2.get(f"/groups/{group_id}")
    assert unauth_get.status_code == 404

    # User 2 tries to update group -> 404
    unauth_patch = auth_client_user2.patch(
        f"/groups/{group_id}",
        json={"name": "Hacked"},
    )
    assert unauth_patch.status_code == 404


def test_group_invitation_flow(
    auth_client_user1,
    auth_client_user2,
    user1,
    user2,
    db,
):
    """Owner invites user2, and user2 accepts invitation."""
    group_res = auth_client_user1.post(
        "/groups/",
        json={"name": "Project Beta", "description": "Beta"},
    )
    group_id = group_res.json()["id"]

    # 1. Invite user2
    invite_res = auth_client_user1.post(
        f"/groups/{group_id}/invite",
        json={"email": user2.email},
    )
    assert invite_res.status_code == 201

    invite_data = invite_res.json()
    token = invite_data["token"]
    assert invite_data["email"] == user2.email

    # 2. Cannot invite yourself
    self_invite = auth_client_user1.post(
        f"/groups/{group_id}/invite",
        json={"email": user1.email},
    )
    assert self_invite.status_code == 400

    # 3. Non-owner cannot invite
    unauth_invite = auth_client_user2.post(
        f"/groups/{group_id}/invite",
        json={"email": "someone@example.com"},
    )
    assert unauth_invite.status_code == 403

    # 4. User 2 accepts invitation
    accept_res = auth_client_user2.get(
        f"/groups/invitations/{token}/accept"
    )
    assert accept_res.status_code == 202
    assert accept_res.json()["message"] == "Invitation accepted successfully."

    # 5. Check members list
    members_res = auth_client_user2.get(f"/groups/{group_id}/members")
    assert members_res.status_code == 200

    member_emails = [m["email"] for m in members_res.json()]
    assert user1.email in member_emails
    assert user2.email in member_emails


def test_group_max_3_members_limit(
    auth_client_user1,
    auth_client_user2,
    auth_client_user3,
    user2,
    user3,
    db,
):
    """Group cannot exceed 3 members limit."""
    group_res = auth_client_user1.post(
        "/groups/",
        json={"name": "Small Team", "description": "Limited to 3"},
    )
    group_id = group_res.json()["id"]

    # Invite and add user2
    inv2 = auth_client_user1.post(
        f"/groups/{group_id}/invite",
        json={"email": user2.email},
    )
    assert inv2.status_code == 201
    auth_client_user2.get(
        f"/groups/invitations/{inv2.json()['token']}/accept"
    )

    # Invite and add user3
    inv3 = auth_client_user1.post(
        f"/groups/{group_id}/invite",
        json={"email": user3.email},
    )
    assert inv3.status_code == 201
    auth_client_user3.get(
        f"/groups/invitations/{inv3.json()['token']}/accept"
    )

    # Group now has 3 members
    user4 = models.Users(
        username="dave",
        email="dave@example.com",
        google_id="gid_dave",
    )
    db.add(user4)
    db.commit()

    # Attempting to invite a 4th member returns 409 Conflict
    inv4 = auth_client_user1.post(
        f"/groups/{group_id}/invite",
        json={"email": user4.email},
    )
    assert inv4.status_code == 409
    assert "Only group of 3 people are only alowed" in inv4.json()["detail"]


def test_leave_group_and_remove_member(
    auth_client_user1,
    auth_client_user2,
    user2,
):
    """Members can leave, and owners can remove members."""
    group_res = auth_client_user1.post(
        "/groups/",
        json={"name": "Dev Ops", "description": "Dev Ops team"},
    )
    group_id = group_res.json()["id"]

    # Invite & accept user2
    inv = auth_client_user1.post(
        f"/groups/{group_id}/invite",
        json={"email": user2.email},
    )
    auth_client_user2.get(
        f"/groups/invitations/{inv.json()['token']}/accept"
    )

    # Owner cannot leave if sole owner -> 400
    owner_leave = auth_client_user1.post(f"/groups/{group_id}/leave")
    assert owner_leave.status_code == 400

    # User 2 leaves
    user2_leave = auth_client_user2.post(f"/groups/{group_id}/leave")
    assert user2_leave.status_code == 200
    assert user2_leave.json()["message"] == "Successfully left the group"

    # User 2 is no longer a member
    unauth_members = auth_client_user2.get(f"/groups/{group_id}/members")
    assert unauth_members.status_code == 403



def test_joined_member_can_get_group_details(
    auth_client_user1,
    auth_client_user2,
    user2,
):
    """A member who joined a group can retrieve its details."""
    group_res = auth_client_user1.post(
        "/groups/",
        json={"name": "Member-visible group", "description": "Visible to members"},
    )
    assert group_res.status_code == 201
    group_id = group_res.json()["id"]

    invite_res = auth_client_user1.post(
        f"/groups/{group_id}/invite",
        json={"email": user2.email},
    )
    assert invite_res.status_code == 201

    accept_res = auth_client_user2.get(
        f"/groups/invitations/{invite_res.json()['token']}/accept"
    )
    assert accept_res.status_code == 202

    details = auth_client_user2.get(f"/groups/{group_id}")
    assert details.status_code == 200
    assert details.json()["id"] == group_id
    assert details.json()["name"] == "Member-visible group"
