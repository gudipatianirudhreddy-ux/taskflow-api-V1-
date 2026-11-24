"""Regression tests for the in-app group invitation and capacity rules."""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException

from app import models, schemas
from app.services import group_invitation_service as invitations


def _make_group(db, owner):
    group = models.Groups(
        name="Capacity regression",
        description="Test group",
        owners_id=owner.id,
    )
    db.add(group)
    db.flush()
    db.add(
        models.Members(
            group_id=group.id,
            user_id=owner.id,
            role=models.Role.owner,
        )
    )
    db.commit()
    db.refresh(group)
    return group


def _make_user(db, number):
    user = models.Users(
        username=f"invitee{number}",
        email=f"invitee{number}@example.com",
        google_id=f"invitee-google-{number}",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _send(db, group, owner, invited):
    group_id = group.id if isinstance(group, models.Groups) else group
    owner_id = owner.id if isinstance(owner, models.Users) else owner
    return invitations.in_group_invitation(
        db,
        schemas.GroupInvitationCreate(email=invited.email),
        group_id,
        owner_id,
    )


def test_in_app_invitation_reserves_capacity(db, user1):
    group = _make_group(db, user1)
    invitees = [_make_user(db, n) for n in range(1, 4)]

    _send(db, group, user1, invitees[0])
    _send(db, group, user1, invitees[1])

    with pytest.raises(HTTPException) as error:
        _send(db, group, user1, invitees[2])
    assert error.value.status_code == 400
    assert error.value.detail == "Group has reached maximum capacity"

    assert (
        db.query(models.InGroupInvitation)
        .filter(
            models.InGroupInvitation.group_id == group.id,
            models.InGroupInvitation.status == models.InvitationStatus.pending,
        )
        .count()
    ) == 2


def test_acceptance_converts_reservation_to_membership(db, user1):
    group = _make_group(db, user1)
    invitees = [_make_user(db, n) for n in range(10, 12)]
    first = _send(db, group, user1, invitees[0])
    second = _send(db, group, user1, invitees[1])

    accepted = invitations.respond_to_invitation(
        db,
        invitees[0].id,
        first.id,
        models.InvitationStatus.accepted,
    )

    assert accepted.status == models.InvitationStatus.accepted
    assert db.query(models.Members).filter_by(group_id=group.id).count() == 2
    assert (
        db.query(models.InGroupInvitation)
        .filter_by(group_id=group.id, status=models.InvitationStatus.pending)
        .count()
    ) == 1
    # One member + one active reservation + owner = group limit 3.
    assert db.query(models.Members).filter_by(group_id=group.id).count() + 1 == 3
    assert second.status == models.InvitationStatus.pending


def test_expired_invitation_status_is_committed(db, user1):
    group = _make_group(db, user1)
    invited = _make_user(db, 20)
    invitation = models.InGroupInvitation(
        group_id=group.id,
        invited_user_id=invited.id,
        invited_by=user1.id,
        status=models.InvitationStatus.pending,
        expires_at=datetime.now(timezone.utc) - timedelta(minutes=1),
    )
    db.add(invitation)
    db.commit()
    db.refresh(invitation)

    with pytest.raises(HTTPException) as error:
        invitations.respond_to_invitation(
            db,
            invited.id,
            invitation.id,
            models.InvitationStatus.accepted,
        )
    assert error.value.status_code == 410

    db.refresh(invitation)
    assert invitation.status == models.InvitationStatus.expired
    assert invitation.responded_at is not None
    assert db.query(models.Members).filter_by(group_id=group.id).count() == 1


def test_rejection_releases_invitation_reservation(db, user1):
    group = _make_group(db, user1)
    invited = _make_user(db, 30)
    invitation = _send(db, group, user1, invited)

    rejected = invitations.respond_to_invitation(
        db,
        invited.id,
        invitation.id,
        models.InvitationStatus.rejected,
    )

    assert rejected.status == models.InvitationStatus.rejected
    assert rejected.responded_at is not None
    assert (
        db.query(models.InGroupInvitation)
        .filter_by(group_id=group.id, status=models.InvitationStatus.pending)
        .count()
    ) == 0


def test_concurrent_invites_cannot_overbook_group(db, user1):
    """PostgreSQL integration regression: only two reservations fit with owner."""
    if db.bind.dialect.name != "postgresql":
        pytest.skip("Row-level FOR UPDATE behavior requires PostgreSQL")

    from tests.conftest import TestingSessionLocal

    group = _make_group(db, user1)
    group_id = group.id
    owner_id = user1.id
    invitees = [_make_user(db, n) for n in range(40, 43)]
    invitee_ids = [user.id for user in invitees]
    start = Barrier(len(invitees))

    def attempt(user_id):
        session = TestingSessionLocal()
        try:
            user = session.query(models.Users).filter_by(id=user_id).one()
            start.wait(timeout=10)
            try:
                _send(session, group_id, owner_id, user)
                return "created"
            except HTTPException as exc:
                assert exc.status_code == 400
                return "capacity"
        finally:
            session.close()

    with ThreadPoolExecutor(max_workers=3) as pool:
        outcomes = list(pool.map(attempt, invitee_ids))

    assert outcomes.count("created") == 2
    assert outcomes.count("capacity") == 1
    assert (
        db.query(models.Members).filter_by(group_id=group.id).count()
        + db.query(models.InGroupInvitation)
        .filter(
            models.InGroupInvitation.group_id == group.id,
            models.InGroupInvitation.status == models.InvitationStatus.pending,
            models.InGroupInvitation.expires_at > datetime.now(timezone.utc),
        )
        .count()
    ) == 3
