from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException

from app import models
from app.services import group_invitation_service


def _create_group_with_owner(db, owner):
    group = models.Groups(
        name="Invitation safety",
        description="Concurrency and expiry checks",
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


def test_expired_in_app_invitation_status_is_persisted(db, user1, user2):
    group = _create_group_with_owner(db, user1)
    invitation = models.InGroupInvitation(
        group_id=group.id,
        invited_user_id=user2.id,
        invited_by=user1.id,
        status=models.InvitationStatus.pending,
        expires_at=datetime.now(timezone.utc) - timedelta(minutes=1),
    )
    db.add(invitation)
    db.commit()
    db.refresh(invitation)

    with pytest.raises(HTTPException) as error:
        group_invitation_service.respond_to_invitation(
            db,
            current_user_id=user2.id,
            invitation_id=invitation.id,
            response=models.InvitationStatus.accepted,
        )

    assert error.value.status_code == 410
    db.refresh(invitation)
    assert invitation.status == models.InvitationStatus.expired


def test_accepting_one_invitation_keeps_other_reserved_seat(db, user1, user2, user3):
    group = _create_group_with_owner(db, user1)
    first = models.InGroupInvitation(
        group_id=group.id,
        invited_user_id=user2.id,
        invited_by=user1.id,
        status=models.InvitationStatus.pending,
        expires_at=datetime.now(timezone.utc) + timedelta(days=2),
    )
    second = models.InGroupInvitation(
        group_id=group.id,
        invited_user_id=user3.id,
        invited_by=user1.id,
        status=models.InvitationStatus.pending,
        expires_at=datetime.now(timezone.utc) + timedelta(days=2),
    )
    db.add_all([first, second])
    db.commit()
    db.refresh(first)
    db.refresh(second)

    result = group_invitation_service.respond_to_invitation(
        db,
        current_user_id=user2.id,
        invitation_id=first.id,
        response=models.InvitationStatus.accepted,
    )
    assert result.status == models.InvitationStatus.accepted

    member_count = (
        db.query(models.Members)
        .filter(models.Members.group_id == group.id)
        .count()
    )
    pending_count = (
        db.query(models.InGroupInvitation)
        .filter(
            models.InGroupInvitation.group_id == group.id,
            models.InGroupInvitation.status == models.InvitationStatus.pending,
        )
        .count()
    )
    assert member_count == 2
    assert pending_count == 1
    assert member_count + pending_count == 3
