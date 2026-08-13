from fastapi import APIRouter, Depends, HTTPException,status
from .. import database,models,schemas
from sqlalchemy.orm import Session
from typing import List
from ..auth import get_current_user
import secrets
from datetime import timedelta, datetime,timezone
from app.services.email_service import send_group_invitation
from app.models import InvitationStatus,Role

router=APIRouter(
    prefix='/groups',
    tags=['Groups']
)

@router.post('/',status_code=status.HTTP_201_CREATED,response_model=schemas.GroupPost)
def create_group(posts: schemas.Group,db: Session = Depends(database.get_db),current_user= Depends(get_current_user)):
    added=models.Groups(**posts.dict(), owners_id=current_user["id"])
    db.add(added)
    db.commit()
    db.refresh(added)
    owner_member=models.Members(group_id=added.id,user_id=current_user["id"],role="owner")
    db.add(owner_member)
    db.commit()
    return added

@router.get('/',status_code=status.HTTP_200_OK, response_model=List[schemas.GroupPost])
def get_groups(db: Session = Depends(database.get_db),current_user= Depends(get_current_user)):
    getting=db.query(models.Groups).filter(models.Groups.owners_id==current_user["id"]).all()
    if not getting:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not authorized or validated")
    
    return getting

@router.get("/{group_id}",status_code=status.HTTP_200_OK, response_model=schemas.GroupPost)
def getting_post(group_id: int, db: Session = Depends(database.get_db),current_user= Depends(get_current_user)):
    post=db.query(models.Groups).filter(models.Groups.id==group_id, models.Groups.owners_id==current_user["id"]).first()
    if not post:
         raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not there or not authorized")
    return post

@router.patch("/{group_id}",status_code=status.HTTP_302_FOUND, response_model=schemas.GroupPost)
def updated_group(group_id: int,posts: schemas.UpdateGroup,db: Session = Depends(database.get_db),current_user= Depends(get_current_user)):
    up=db.query(models.Groups).filter(models.Groups.id==group_id, models.Groups.owners_id==current_user["id"])
    updates=posts.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(
              status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields provided for update"
        )
    if not up.first():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found or group not found")
    up.update(updates, synchronize_session=False)
    db.commit()
    return up.first()

@router.delete("/{group_id}", status_code=status.HTTP_202_ACCEPTED,response_model=schemas.GroupPost)
def delete(group_id: int, db: Session = Depends(database.get_db),current_user= Depends(get_current_user)):
     deli=db.query(models.Groups).filter(models.Groups.id==group_id, models.Groups.owners_id==current_user["id"]).first()
     if not deli:
          raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invalid id or id do not exist")
     db.delete(deli)
     db.commit()
     return {"Messsage":"Deleted the group Sucessfully"}

@router.post("/{group_id}/invite", status_code=status.HTTP_201_CREATED,response_model=schemas.GroupInvitationResponse)
def send_invite(invite: schemas.GroupInvitationBase,group_id: int,db: Session = Depends(database.get_db),current_user= Depends(get_current_user)):
    ans=db.query(models.Groups).filter(models.Groups.id==group_id).first()
    if not ans:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group dosen't exists")
    if ans.owners_id!=current_user["id"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User not validate or nnot loggined")
    user=db.query(models.Users).filter(models.Users.email==invite.email).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User does not exists")
    if user.id==current_user["id"]:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="You  cannot invite yourself")
    pending=db.query(models.GroupInvitation).filter( models.GroupInvitation.group_id==group_id, models.GroupInvitation.email==invite.email,models.GroupInvitation.status==InvitationStatus.pending
                                                    ).first()
    if pending:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,detail="Invitation already sent")
    modes=(db.query(models.Members).filter(models.Members.group_id==group_id,models.Members.user_id==user.id).first())
    if modes:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User already exists in the group")
    people=db.query(models.Members).filter(models.Members.group_id==group_id).count()
    if people>=3:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Only group of 3 people are only alowed")
    token=secrets.token_urlsafe(32)
    expires_at=datetime.now(timezone.utc) + timedelta(days=7)
    invite_obj=models.GroupInvitation(
         group_id=group_id,
         email=invite.email,
         invited_by=current_user["id"],
         token=token,
        expires_at=expires_at
    )
    db.add(invite_obj)
    db.commit()
    db.refresh(invite_obj)
    accept_url =f"https://taskflow-api-v1-225t.onrender.com/groups/invitations/{token}/accept"
    try:
        inviter=db.query(models.Users).filter(models.Users.id==current_user["id"]).first()
        send_group_invitation(
            to_email=invite.email,
             inviter_email=inviter.email,
              group_name=ans.name,
              accept_url=accept_url
        )
    except Exception as e:
         db.delete(invite_obj)
         db.commit()
         raise  HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,detail=f"Failed to send invitation: {str(e)}")
     
         
        
    return invite_obj


@router.get("/invitations/{token}/accept", status_code=status.HTTP_202_ACCEPTED)
def accept_invitation(token: str,db: Session = Depends(database.get_db),current_user= Depends(get_current_user)):
    qr1=db.query(models.GroupInvitation).filter(models.GroupInvitation.token==token).first()
    if not qr1:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    if qr1.status != InvitationStatus.pending:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invitation is no longer pending.")
    if qr1.expires_at < datetime.now(timezone.utc):
        qr1.status=InvitationStatus.expired
        db.commit()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invitation has expired")
    qr2=db.query(models.Users).filter(models.Users.id==current_user["id"]).first()
    if qr2.email!=qr1.email:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
    qr3=db.query(models.Members).filter(models.Members.group_id==qr1.group_id, models.Members.user_id==qr2.id).first()
    if qr3:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User is already a member of this group.")
    people=db.query(models.Members).filter(models.Members.group_id==qr1.group_id).count()
    if people>=3:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Only group of 3 people are only alowed")
    new_member=models.Members(
        group_id=qr1.group_id,
        user_id=current_user["id"],
        role=Role.member
    )
    db.add(new_member)
    qr1.status=InvitationStatus.accepted
    db.commit()
    db.refresh(new_member)
    return {"message":"Invitation accepted successfully."}


@router.get("/{group_id}/members", status_code=status.HTTP_200_OK, response_model=List[schemas.GroupMemberResponse])
def get_group_members(group_id: int, db: Session = Depends(database.get_db), current_user=Depends(get_current_user)):
    group = db.query(models.Groups).filter(models.Groups.id == group_id).first()
    if not group:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group does not exist")

    is_member = db.query(models.Members).filter(
        models.Members.group_id == group_id,
        models.Members.user_id == current_user["id"]
    ).first()
    if not is_member:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You are not a member of this group")

    members = db.query(
        models.Users.id,
        models.Users.username,
        models.Users.email,
        models.Members.role,
        models.Members.joined_at
    ).join(
        models.Members, models.Users.id == models.Members.user_id
    ).filter(
        models.Members.group_id == group_id
    ).all()

    return members


@router.post("/{group_id}/leave", status_code=status.HTTP_200_OK, response_model=schemas.MessageResponse)
def leave_group(group_id: int, db: Session = Depends(database.get_db), current_user=Depends(get_current_user)):
    group = db.query(models.Groups).filter(models.Groups.id == group_id).first()
    if not group:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group does not exist")

    member = db.query(models.Members).filter(
        models.Members.group_id == group_id,
        models.Members.user_id == current_user["id"]
    ).first()
    if not member:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="You are not a member of this group")

    if member.role == Role.owner:
        owner_count = db.query(models.Members).filter(
            models.Members.group_id == group_id,
            models.Members.role == Role.owner
        ).count()
        if owner_count <= 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Group owner cannot leave the group if they are the only owner"
            )

    db.delete(member)
    db.commit()
    return {"message": "Successfully left the group"}


@router.delete("/{group_id}/members/{user_id}", status_code=status.HTTP_200_OK, response_model=schemas.MessageResponse)
def remove_group_member(group_id: int, user_id: int, db: Session = Depends(database.get_db), current_user=Depends(get_current_user)):
    group = db.query(models.Groups).filter(models.Groups.id == group_id).first()
    if not group:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group does not exist")

    current_member = db.query(models.Members).filter(
        models.Members.group_id == group_id,
        models.Members.user_id == current_user["id"]
    ).first()
    if not current_member or current_member.role != Role.owner:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the group owner can remove members")

    target_member = db.query(models.Members).filter(
        models.Members.group_id == group_id,
        models.Members.user_id == user_id
    ).first()
    if not target_member:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Target user is not a member of this group")

    if target_member.role == Role.owner:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot remove group owner")

    db.delete(target_member)
    db.commit()
    return {"message": "Member removed successfully"}


@router.post("/{group_id}/tasks",  status_code=status.HTTP_201_CREATED, response_model=schemas.GroupTaskResponse)
def make_tasks(group_id: int ,posts: schemas.GroupTasksCreate,db: Session = Depends(database.get_db), current_user=Depends(get_current_user)):
    group=db.query(models.Groups).filter(models.Groups.id==group_id).first()
    if not group:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found")
    memeber=db.query(models.Members).filter(models.Members.group_id==group_id, models.Members.user_id==current_user["id"]).first()
    if not memeber:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Member does not belong to this group")
    if group.owners_id != current_user["id"]:
           raise HTTPException(
                          status_code=403,
                          detail="Only the group owner can create tasks."
            )
    verify=db.query(models.Members).filter(models.Members.group_id==group_id, models.Members.user_id==posts.assigned_to).first()
    if not verify:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User is not the member of this group")
    ans=models.GroupTask(**posts.dict(), group_id=group_id,created_by=current_user["id"])
    db.add(ans)
    db.commit()
    db.refresh(ans)
    return ans


@router.get("/{group_id}/tasks", status_code=status.HTTP_200_OK, response_model=List[schemas.GroupTaskResponse])
def get_group_tasks(group_id: int, db: Session = Depends(database.get_db), current_user=Depends(get_current_user)):
    group = db.query(models.Groups).filter(models.Groups.id == group_id).first()
    if not group:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found")

    member = db.query(models.Members).filter(
        models.Members.group_id == group_id,
        models.Members.user_id == current_user["id"]
    ).first()
    if not member:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You are not a member of this group")

    if group.owners_id == current_user["id"]:
        tasks = db.query(models.GroupTask).filter(models.GroupTask.group_id == group_id).all()
    else:
        tasks = db.query(models.GroupTask).filter(
            models.GroupTask.group_id == group_id,
            models.GroupTask.assigned_to == current_user["id"]
        ).all()

    return tasks


@router.get("/{group_id}/tasks/{task_id}", status_code=status.HTTP_200_OK, response_model=schemas.GroupTaskResponse)
def get_group_task(group_id: int, task_id: int, db: Session = Depends(database.get_db), current_user=Depends(get_current_user)):
    group = db.query(models.Groups).filter(models.Groups.id == group_id).first()
    if not group:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found")

    member = db.query(models.Members).filter(
        models.Members.group_id == group_id,
        models.Members.user_id == current_user["id"]
    ).first()
    if not member:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You are not a member of this group")

    task = db.query(models.GroupTask).filter(
        models.GroupTask.id == task_id,
        models.GroupTask.group_id == group_id
    ).first()
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found in this group")

    if group.owners_id != current_user["id"] and task.assigned_to != current_user["id"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You are not authorized to view this task")

    return task


@router.patch("/{group_id}/tasks/{task_id}", status_code=status.HTTP_200_OK, response_model=schemas.GroupTaskResponse)
def update_group_task(
    group_id: int,
    task_id: int,
    task_update: schemas.GroupTaskUpdate,
    db: Session = Depends(database.get_db),
    current_user=Depends(get_current_user)
):
    group = db.query(models.Groups).filter(models.Groups.id == group_id).first()
    if not group:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found")

    member = db.query(models.Members).filter(
        models.Members.group_id == group_id,
        models.Members.user_id == current_user["id"]
    ).first()
    if not member:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You are not a member of this group")

    task = db.query(models.GroupTask).filter(
        models.GroupTask.id == task_id,
        models.GroupTask.group_id == group_id
    ).first()
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found in this group")

    is_owner = (group.owners_id == current_user["id"])
    is_assigned = (task.assigned_to == current_user["id"])

    if not is_owner and not is_assigned:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You are not authorized to update this task")

    update_data = task_update.model_dump(exclude_unset=True)

    if not is_owner:
        if "assigned_to" in update_data and update_data["assigned_to"] != task.assigned_to:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Members cannot reassign tasks")

    if "assigned_to" in update_data and update_data["assigned_to"] is not None:
        target_member = db.query(models.Members).filter(
            models.Members.group_id == group_id,
            models.Members.user_id == update_data["assigned_to"]
        ).first()
        if not target_member:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Assigned user is not a member of this group")

    for key, value in update_data.items():
        setattr(task, key, value)

    db.commit()
    db.refresh(task)
    return task


@router.delete("/{group_id}/tasks/{task_id}", status_code=status.HTTP_200_OK, response_model=schemas.MessageResponse)
def delete_group_task(group_id: int, task_id: int, db: Session = Depends(database.get_db), current_user=Depends(get_current_user)):
    group = db.query(models.Groups).filter(models.Groups.id == group_id).first()
    if not group:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found")

    member = db.query(models.Members).filter(
        models.Members.group_id == group_id,
        models.Members.user_id == current_user["id"]
    ).first()
    if not member:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You are not a member of this group")

    task = db.query(models.GroupTask).filter(
        models.GroupTask.id == task_id,
        models.GroupTask.group_id == group_id
    ).first()
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found in this group")

    if group.owners_id != current_user["id"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the group owner can delete tasks")

    db.delete(task)
    db.commit()
    return {"message": "Task deleted successfully"}


@router.get("/{group_id}/my-tasks",status_code=status.HTTP_200_OK,response_model=List[schemas.GroupTaskResponse])
def get_my_tasks(group_id: int, db: Session = Depends(database.get_db),current_user=Depends(get_current_user)):
    group = db.query(models.Groups).filter(models.Groups.id == group_id).first()
    if not group:
          raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,detail="Group not found")
    member = db.query(models.Members).filter(models.Members.group_id == group_id,models.Members.user_id == current_user["id"]).first()
    if not member:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,detail="You are not a member of this group")
    tasks = db.query(models.GroupTask).filter(models.GroupTask.group_id == group_id,models.GroupTask.assigned_to == current_user["id"]).all()
    return tasks