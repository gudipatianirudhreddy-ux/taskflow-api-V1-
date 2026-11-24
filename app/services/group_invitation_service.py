"""Transactional services for the platform-dependent group invitation flow.

Capacity rule: a group has at most three people (including its owner). Pending,
unexpired in-app invitations reserve a place. All operations that can consume a
place lock the Group row first; PostgreSQL serializes those operations per group.
"""
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app import models, schemas


MAX_GROUP_SIZE = 3
INVITATION_TTL = timedelta(days=5)


def _utc(value: datetime) -> datetime:
    """Normalize DB timestamps; some drivers return naive UTC datetimes."""
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _lock_group(db: Session, group_id: int):
    """Acquire the shared capacity mutex (a row lock on the Group record)."""
    group = (
        db.query(models.Groups)
        .filter(models.Groups.id == group_id)
        .with_for_update()
        .populate_existing()
        .first()
    )
    if group is None:
        raise HTTPException(status_code=404, detail="Group not found")
    return group


def _capacity_counts(
    db: Session,
    group_id: int,
    *,
    exclude_invitation_id: int | None = None,
) -> tuple[int, int]:
    now = datetime.now(timezone.utc)
    members = (
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
    pending = pending_query.count()
    return members, pending


def in_group_invitation(
    db: Session,
    invitation_data: schemas.GroupInvitationCreate,
    group_id: int,
    current_user_id: int,
):
    now = datetime.now(timezone.utc)
    try:
        # The group row is the common lock for invitation reservations and
        # invitation acceptance. Lock before counting or writing capacity.
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
        if invited_user is None:
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
                existing_invitation.responded_at = now
                db.flush()
            else:
                raise HTTPException(
                    status_code=409,
                    detail="An invitation is already pending for this user in the group",
                )

        member_count, pending_count = _capacity_counts(db, group_id)
        if member_count + pending_count >= MAX_GROUP_SIZE:
            raise HTTPException(
                status_code=400,
                detail="Group has reached maximum capacity",
            )

        invitation = models.InGroupInvitation(
            group_id=group_id,
            invited_user_id=invited_user.id,
            invited_by=current_user_id,
            status=models.InvitationStatus.pending,
            expires_at=now + INVITATION_TTL,
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
    return (
        db.query(models.InGroupInvitation)
        .filter(
            models.InGroupInvitation.invited_user_id == current_user_id,
            models.InGroupInvitation.status == models.InvitationStatus.pending,
            models.InGroupInvitation.expires_at > now,
        )
        .all()
    )


def add_member(
    db: Session,
    current_user_id: int,
    group_id: int,
    *,
    exclude_invitation_id: int | None = None,
):
    """Add a member while holding the group's capacity lock.

    When accepting an invitation, exclude that invitation from pending
    reservations because it is atomically converted into the new membership.
    """
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

    member_count, pending_count = _capacity_counts(
        db, group_id, exclude_invitation_id=exclude_invitation_id
    )
    if member_count + pending_count >= MAX_GROUP_SIZE:
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
    # Initial read obtains immutable group_id. Always lock Group before
    # locking the invitation to keep a consistent lock order.
    invitation_ref = (
        db.query(models.InGroupInvitation)
        .filter(
            models.InGroupInvitation.id == invitation_id,
            models.InGroupInvitation.invited_user_id == current_user_id,
        )
        .first()
    )
    if invitation_ref is None:
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
            .populate_existing()
            .first()
        )
        if invitation is None:
            raise HTTPException(status_code=404, detail="Invitation not found")
        if invitation.status != models.InvitationStatus.pending:
            raise HTTPException(
                status_code=409,
                detail="Invitation is no longer pending",
            )

        now = datetime.now(timezone.utc)
        if _utc(invitation.expires_at) <= now:
            invitation.status = models.InvitationStatus.expired
            invitation.responded_at = now
            db.commit()  # Persist expiry before returning the 410 response.
            raise HTTPException(status_code=410, detail="Invitation has expired")

        if response == models.InvitationStatus.accepted:
            add_member(
                db,
                current_user_id,
                invitation.group_id,
                exclude_invitation_id=invitation.id,
            )
        elif response != models.InvitationStatus.rejected:
            raise HTTPException(status_code=400, detail="Invalid invitation response")

        invitation.status = response
        invitation.responded_at = now
        db.commit()
        db.refresh(invitation)
        return invitation
    except Exception:
        db.rollback()
        raise
