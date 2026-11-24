
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app import models, schemas


def in_group_invitation(
    db: Session,
    invitation_data: schemas.GroupInvitationCreate,
    group_id: int,
    current_user_id: int,
):
    now = datetime.now(timezone.utc)

    group = _lock_group_for_capacity(db, group_id)

    if not group:
        raise HTTPException(status_code=404, detail="Group not found")

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
        raise HTTPException(
            status_code=400,
            detail="You cannot invite yourself",
        )

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
        .first()
    )

    if existing_invitation:
        if existing_invitation.expires_at <= now:
            existing_invitation.status = models.InvitationStatus.expired
            db.flush()
        else:
            raise HTTPException(
                status_code=409,
                detail="An invitation is already pending for this user in the group",
            )
    members_count=(db.query(models.Members).filter(models.Members.group_id==group_id).count())
    pending_count=(db.query(models.InGroupInvitation).filter(models.InGroupInvitation.group_id==group_id,
                                                             models.InGroupInvitation.status==models.InvitationStatus.pending,
                                                             models.InGroupInvitation.expires_at>now).count())
    if members_count+pending_count>=3:
        raise HTTPException(status_code=400, detail="Group has reached maximum capacity")
    

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


def user_invitation( db: Session, current_user_id: int):
    invitations=db.query(models.InGroupInvitation).filter(models.InGroupInvitation.invited_user_id==current_user_id,models.InGroupInvitation.status==models.InvitationStatus.pending).all()
    return invitations

def add_member(db: Session, current_user_id: int,group_id: int):
    group= _lock_group_for_capacity(db, group_id)
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    existing_member=db.query(models.Members).filter(models.Members.group_id==group_id,models.Members.user_id==current_user_id).first()
    if existing_member:
        raise HTTPException(status_code=400, detail="Already a member")
    members_count=(db.query(models.Members).filter(models.Members.group_id==group_id).count())
    if members_count>=3:
        raise HTTPException(status_code=400, detail="Group has reached maximum capacity")
    member=models.Members(
        group_id=group_id,
        user_id=current_user_id,
        role=models.Role.member
    )
    db.add(member)
    db.flush()
    return member


def respond_to_invitation(db:Session,current_user_id: int,invitation_id: int, response: models.InvitationStatus):
    invitation=db.query(models.InGroupInvitation).filter(models.InGroupInvitation.id==invitation_id,models.InGroupInvitation.invited_user_id==current_user_id).first()
    if not invitation:
        raise HTTPException(status_code=404, detail="Invitation not found")
    group_id = invitation.group_id
    group= _lock_group_for_capacity(db, group_id)
    if not group:
        raise HTTPException(status_code=404,detail="Group not found")
    db.query(models.InGroupInvitation).filter(models.InGroupInvitation.id==invitation_id,models.InGroupInvitation.invited_user_id==current_user_id).with_for_update().populate_existing().first()
    if not invitation:
            raise HTTPException(status_code=404, detail="Invitation not found")
    now=datetime.now(timezone.utc)
    if invitation.status!=models.InvitationStatus.pending:
        raise HTTPException(status_code=409, detail="Invitation is no longer pending")
    if invitation.expires_at<=now :
        invitation.status=models.InvitationStatus.expired
        db.commit()
        raise HTTPException(status_code=404, detail="Invitations is expired")
    if response==models.InvitationStatus.accepted:
        add_member(db,current_user_id,invitation.group_id)
    elif response==models.InvitationStatus.rejected:
        pass
    else:
        raise HTTPException(status_code=400, detail="Invalid response time")
    invitation.status=response
    invitation.responded_at=now
    db.commit()
    db.refresh(invitation)
    return invitation

def _lock_group_for_capacity(db: Session, group_id: int):
    return (
        db.query(models.Groups)
        .filter(models.Groups.id == group_id)
        .with_for_update()
        .first()
    )


    