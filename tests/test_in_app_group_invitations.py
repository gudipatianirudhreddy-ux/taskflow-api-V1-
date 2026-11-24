"""Regression tests for the registered-user, in-app group invitation flow."""

from datetime import datetime, timedelta, timezone

from app import models


def _create_group(client, name="Invitation test group"):
    response = client.post(
        "/groups/",
        json={"name": name, "description": "Invitation test"},
    )
    assert response.status_code == 201
    return response.json()["id"]


def _send_invitation(client, group_id, email):
    return client.post(
        f"/groups/{group_id}/invite",
        json={"email": email},
    )


def test_invitation_appears_in_recipient_inbox(
    auth_client_user1, auth_client_user2, user2
):
    group_id = _create_group(auth_client_user1)
    created = _send_invitation(auth_client_user1, group_id, user2.email)

    assert created.status_code == 201
    invitation = created.json()
    assert invitation["group_id"] == group_id
    assert invitation["invited_by"] > 0
    assert invitation["status"] == "pending"

    inbox = auth_client_user2.get("/groups/invitations")
    assert inbox.status_code == 200
    assert [item["id"] for item in inbox.json()] == [invitation["id"]]


def test_only_group_owner_can_send_in_app_invitation(
    auth_client_user1, auth_client_user2, user2
):
    group_id = _create_group(auth_client_user1)

    response = _send_invitation(auth_client_user2, group_id, user2.email)

    assert response.status_code == 403
    assert response.json()["detail"] == "Only owners can send invitations"


def test_invitation_rejects_unknown_user(auth_client_user1):
    group_id = _create_group(auth_client_user1)

    response = _send_invitation(
        auth_client_user1, group_id, "not-registered@example.com"
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "User not found"


def test_duplicate_pending_invitation_is_conflict(
    auth_client_user1, user2
):
    group_id = _create_group(auth_client_user1)

    first = _send_invitation(auth_client_user1, group_id, user2.email)
    second = _send_invitation(auth_client_user1, group_id, user2.email)

    assert first.status_code == 201
    assert second.status_code == 409
    assert "already pending" in second.json()["detail"]


def test_recipient_acceptance_creates_membership_and_updates_invitation(
    auth_client_user1, auth_client_user2, user2, db
):
    group_id = _create_group(auth_client_user1)
    created = _send_invitation(auth_client_user1, group_id, user2.email)
    invitation_id = created.json()["id"]

    response = auth_client_user2.patch(
        f"/groups/invitations/{invitation_id}/respond",
        json={"status": "accepted"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "accepted"
    assert response.json()["responded_at"] is not None

    membership = (
        db.query(models.Members)
        .filter_by(group_id=group_id, user_id=user2.id)
        .first()
    )
    assert membership is not None
    assert membership.role == models.Role.member


def test_recipient_rejection_updates_invitation_without_membership(
    auth_client_user1, auth_client_user2, user2, db
):
    group_id = _create_group(auth_client_user1)
    created = _send_invitation(auth_client_user1, group_id, user2.email)
    invitation_id = created.json()["id"]

    response = auth_client_user2.patch(
        f"/groups/invitations/{invitation_id}/respond",
        json={"status": "rejected"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "rejected"
    assert response.json()["responded_at"] is not None
    assert (
        db.query(models.Members)
        .filter_by(group_id=group_id, user_id=user2.id)
        .first()
        is None
    )


def test_invitation_cannot_be_responded_to_by_another_user(
    auth_client_user1, auth_client_user2, auth_client_user3, user2
):
    group_id = _create_group(auth_client_user1)
    created = _send_invitation(auth_client_user1, group_id, user2.email)

    response = auth_client_user3.patch(
        f"/groups/invitations/{created.json()['id']}/respond",
        json={"status": "accepted"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Invitation not found"


def test_invitation_cannot_be_responded_to_twice(
    auth_client_user1, auth_client_user2, user2
):
    group_id = _create_group(auth_client_user1)
    created = _send_invitation(auth_client_user1, group_id, user2.email)
    invitation_id = created.json()["id"]

    first = auth_client_user2.patch(
        f"/groups/invitations/{invitation_id}/respond",
        json={"status": "rejected"},
    )
    second = auth_client_user2.patch(
        f"/groups/invitations/{invitation_id}/respond",
        json={"status": "accepted"},
    )

    assert first.status_code == 200
    assert second.status_code == 409
    assert second.json()["detail"] == "Invitation is no longer pending"


def test_response_rejects_invalid_status(
    auth_client_user1, auth_client_user2, user2
):
    group_id = _create_group(auth_client_user1)
    created = _send_invitation(auth_client_user1, group_id, user2.email)

    response = auth_client_user2.patch(
        f"/groups/invitations/{created.json()['id']}/respond",
        json={"status": "maybe"},
    )

    assert response.status_code == 422
