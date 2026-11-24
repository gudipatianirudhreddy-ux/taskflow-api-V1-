from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app import models, schemas


def _utc(value: datetime) -> datetime:
    """Treat timezone-naive database timestamps as UTC (SQLite parity)."""
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _lock_group(db: Session, group_id: int):
    """Serialize capacity-changing operations for a group."""
    group = (
        db.query(models.Groups)
        .filter(models.Groups.id == group_id)
        .with_for_update()
        .first()
    )
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    return group


def in_group_invitation(
    db: Session,
    invitation_data: schemas.GroupInvitationCreate,
    group_id: int,
    current_user_id: int,
):
    now = datetime.now(timezone.utc)

    try:
        # Lock first: concurrent invitation sends / accepts / member adds for
        # this group must queue before counting capacity.
        group = _lock_group(db, group_id)

        if group.owners_id != current_user_id:
            raise HTTPException(
                status_code=403,
                detail="Only owners can send invitations",
            )

        invited_user = (
            db.query(models.Users)
            .filter(models.Users.email == invitation_data.email)
            .first()
        )
        if not invited_user:
            raise HTTPException(status_code=404, detail="User not found")
        if invited_user.id == current_user_id:
            raise HTTPException(status_code=400, detail="You cannot invite yourself")

        existing_member = (
            db.query(models.Members)
            .filter(
                models.Members.group_id == group_id,
                models.Members.user_id == invited_user.id,
            )
            .first()
        )
        if existing_member:
            raise HTTPException(
                status_code=409,
                detail="User is already a member of the group",
            )

        existing_invitation = (
            db.query(models.InGroupInvitation)
            .filter(
                models.InGroupInvitation.group_id == group_id,
                models.InGroupInvitation.invited_user_id == invited_user.id,
                models.InGroupInvitation.status == models.InvitationStatus.pending,
            )
            .with_for_update()
            .first()
        )
        if existing_invitation:
            if _utc(existing_invitation.expires_at) <= now:
                existing_invitation.status = models.InvitationStatus.expired
                db.flush()
            else:
                raise HTTPException(
                    status_code=409,
                    detail="An invitation is already pending for this user in the group",
                )

        members_count = (
            db.query(models.Members)
            .filter(models.Members.group_id == group_id)
            .count()
        )
        pending_count = (
            db.query(models.InGroupInvitation)
            .filter(
                models.InGroupInvitation.group_id == group_id,
                models.InGroupInvitation.status == models.InvitationStatus.pending,
                models.InGroupInvitation.expires_at > now,
            )
            .count()
        )
        if members_count + pending_count >= 3:
            raise HTTPException(
                status_code=400,
                detail="Group has reached maximum capacity",
            )

        invitation = models.InGroupInvitation(
            group_id=group_id,
            invited_user_id=invited_user.id,
            invited_by=current_user_id,
            status=models.InvitationStatus.pending,
            expires_at=now + timedelta(days=5),
        )
        db.add(invitation)
        db.commit()
        db.refresh(invitation)
        return invitation
    except Exception:
        db.rollback()
        raise


def user_invitation(db: Session, current_user_id: int):
    now = datetime.now(timezone.utc)
    invitations = (
        db.query(models.InGroupInvitation)
        .filter(
            models.InGroupInvitation.invited_user_id == current_user_id,
            models.InGroupInvitation.status == models.InvitationStatus.pending,
            models.InGroupInvitation.expires_at > now,
        )
        .all()
    )
    return invitations


def add_member(\n    db: Session,\n    current_user_id: int,\n    group_id: int,\n    exclude_invitation_id: int | None = None,\n):
    # This function also locks the group so other membership-adding paths
    # participate in the same capacity serialization.
    _lock_group(db, group_id)

    existing_member = (
        db.query(models.Members)
        .filter(
            models.Members.group_id == group_id,
            models.Members.user_id == current_user_id,
        )
        .first()
    )
    if existing_member:
        raise HTTPException(status_code=409, detail="Already a member")

    now = datetime.now(timezone.utc)
    members_count = (
        db.query(models.Members)
        .filter(models.Members.group_id == group_id)
        .count()
    )
    pending_query = db.query(models.InGroupInvitation).filter(
        models.InGroupInvitation.group_id == group_id,
        models.InGroupInvitation.status == models.InvitationStatus.pending,
        models.InGroupInvitation.expires_at > now,
    )
    if exclude_invitation_id is not None:
        pending_query = pending_query.filter(
            models.InGroupInvitation.id != exclude_invitation_id
        )
    pending_count = pending_query.count()

    # Active invitations reserve capacity. Exclude the invitation being
    # accepted because it is transitioning from pending to membership.
    if members_count + pending_count >= 3:
        raise HTTPException(
            status_code=400,
            detail="Group has reached maximum capacity",
        )

    member = models.Members(
        group_id=group_id,
        user_id=current_user_id,
        role=models.Role.member,
    )
    db.add(member)
    db.flush()
    return member


def respond_to_invitation(
    db: Session,
    current_user_id: int,
    invitation_id: int,
    response: models.InvitationStatus,
):
    # Read the group id, then lock group first (consistent lock order), and
    # re-read/lock the invitation after waiting for the group lock.
    invitation_ref = (
        db.query(models.InGroupInvitation)
        .filter(
            models.InGroupInvitation.id == invitation_id,
            models.InGroupInvitation.invited_user_id == current_user_id,
        )
        .first()
    )
    if not invitation_ref:
        raise HTTPException(status_code=404, detail="Invitation not found")

    try:
        _lock_group(db, invitation_ref.group_id)
        invitation = (
            db.query(models.InGroupInvitation)
            .filter(
                models.InGroupInvitation.id == invitation_id,
                models.InGroupInvitation.invited_user_id == current_user_id,
            )
            .with_for_update()
            .first()
        )
        if not invitation:
            raise HTTPException(status_code=404, detail="Invitation not found")

        now = datetime.now(timezone.utc)
        if invitation.status != models.InvitationStatus.pending:
            raise HTTPException(
                status_code=409,
                detail="Invitation is no longer pending",
            )

        if _utc(invitation.expires_at) <= now:
            invitation.status = models.InvitationStatus.expired
            invitation.responded_at = now
            db.commit()  # persist expiry before returning the HTTP error
            raise HTTPException(status_code=410, detail="Invitation has expired")

        if response == models.InvitationStatus.accepted:
            add_member(\n                db, current_user_id, invitation.group_id,\n                exclude_invitation_id=invitation.id,\n            )
        elif response != models.InvitationStatus.rejected:
            raise HTTPException(status_code=400, detail="Invalid invitation response")

        invitation.status = response
        invitation.responded_at = now
        db.commit()
        db.refresh(invitation)
        return invitation
    except HTTPException:
        # Expiry is already committed above; rollback is harmless after commit.
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise
