from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.responses import HTMLResponse
from .. import database,models,schemas
from sqlalchemy.orm import Session
from typing import List
from ..auth import get_current_user
import secrets
from html import escape
import os
from datetime import timedelta, datetime,timezone
from app.services.email_service import send_group_invitation
from app.models import InvitationStatus,Role
from app.services import group_invitation_service
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
    getting=db.query(models.Groups).join(models.Members,models.Groups.id==models.Members.group_id).filter(models.Members.user_id==current_user["id"]).all()

    return getting

@router.get("/invitations",response_model=list[schemas.InGroupInvitationResponse])
def get_invitations(db: Session=Depends(database.get_db), current_user=Depends(get_current_user)):
    invitations=group_invitation_service.user_invitation(db=db,current_user_id=current_user["id"])
    return invitations

@router.get("/{group_id}",status_code=status.HTTP_200_OK, response_model=schemas.GroupPost)
def getting_post(group_id: int, db: Session = Depends(database.get_db),current_user= Depends(get_current_user)):
    post=db.query(models.Groups).join(models.Members,models.Groups.id==models.Members.group_id).filter(models.Members.user_id==current_user["id"],models.Groups.id==group_id).first()
    if not post:
         raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not there or not authorized")
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

@router.post("/{group_id}/invite", status_code=status.HTTP_201_CREATED,response_model=schemas.InGroupInvitationResponse)
def send_invite(invite: schemas.GroupInvitationBase,group_id: int,db: Session = Depends(database.get_db),current_user= Depends(get_current_user)):
    invitation=group_invitation_service.in_group_invitation(db=db,invitation_data=invite,group_id=group_id,current_user_id=current_user["id"])
    return invitation
    
@router.patch("/invitations/{invitation_id}/respond",response_model=schemas.InGroupInvitationResponse)
def respond_to_invitation(invitation_id: int,response:schemas.GroupInvitationRespond ,db: Session=Depends(database.get_db),current_user= Depends(get_current_user)):
    inv=group_invitation_service.respond_to_invitation(db=db,
                                                        current_user_id=current_user["id"],
                                                        invitation_id=invitation_id,
                                                        response=response.status)
    return inv
    


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
    if group.owners_id != current_user["id"] and memeber.role != models.Role.admin:
           raise HTTPException(
                          status_code=403,
                          detail="Only the group owner or admin can create tasks."
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

    if group.owners_id == current_user["id"] or  member.role == models.Role.admin:
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

    if group.owners_id != current_user["id"] and  member.role != models.Role.admin and task.assigned_to != current_user["id"]:
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
    is_admin = (member.role == models.Role.admin)
    is_assigned = (task.assigned_to == current_user["id"])

    if not is_owner and not is_admin and not is_assigned:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You are not authorized to update this task")

    update_data = task_update.model_dump(exclude_unset=True)

    if not is_owner and not is_admin:
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


@router.post("/{group_id}/tasks/{task_id}/subtasks", status_code=status.HTTP_201_CREATED, response_model=schemas.GroupSubtaskResponse)
def create_group_subtask(
    group_id: int,
    task_id: int,
    subtask: schemas.GroupSubtaskCreate,
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

    if group.owners_id != current_user["id"] and member.role != models.Role.admin and task.assigned_to != current_user["id"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You are not authorized to add subtasks to this task")

    subtask_data = subtask.model_dump(exclude_unset=True)
    subtask_data["group_task_id"] = task_id
    new_subtask = models.GroupSubtask(**subtask_data)
    db.add(new_subtask)
    db.commit()
    db.refresh(new_subtask)
    return new_subtask


@router.get("/{group_id}/tasks/{task_id}/subtasks", status_code=status.HTTP_200_OK, response_model=List[schemas.GroupSubtaskResponse])
def get_group_subtasks(
    group_id: int,
    task_id: int,
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

    if group.owners_id != current_user["id"] and member.role != models.Role.admin and task.assigned_to != current_user["id"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You are not authorized to view subtasks for this task")

    subtasks = db.query(models.GroupSubtask).filter(models.GroupSubtask.group_task_id == task_id).all()
    return subtasks


@router.patch("/{group_id}/tasks/subtasks/{subtask_id}", status_code=status.HTTP_200_OK, response_model=schemas.GroupSubtaskResponse)
def update_group_subtask(
    group_id: int,
    subtask_id: int,
    subtask_update: schemas.GroupSubtaskUpdate,
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

    subtask = (
        db.query(models.GroupSubtask)
        .join(models.GroupTask, models.GroupSubtask.group_task_id == models.GroupTask.id)
        .filter(
            models.GroupSubtask.id == subtask_id,
            models.GroupTask.group_id == group_id
        )
        .first()
    )
    if not subtask:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subtask not found in this group")

    task = db.query(models.GroupTask).filter(models.GroupTask.id == subtask.group_task_id).first()
    if group.owners_id != current_user["id"] and member.role != models.Role.admin and task.assigned_to != current_user["id"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You are not authorized to update this subtask")

    update_data = subtask_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(subtask, key, value)

    db.commit()
    db.refresh(subtask)
    return subtask


@router.delete("/{group_id}/tasks/subtasks/{subtask_id}", status_code=status.HTTP_200_OK, response_model=schemas.MessageResponse)
def delete_group_subtask(
    group_id: int,
    subtask_id: int,
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

    subtask = (
        db.query(models.GroupSubtask)
        .join(models.GroupTask, models.GroupSubtask.group_task_id == models.GroupTask.id)
        .filter(
            models.GroupSubtask.id == subtask_id,
            models.GroupTask.group_id == group_id
        )
        .first()
    )
    if not subtask:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subtask not found in this group")

    task = db.query(models.GroupTask).filter(models.GroupTask.id == subtask.group_task_id).first()
    if group.owners_id != current_user["id"] and task.assigned_to != current_user["id"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You are not authorized to delete this subtask")

    db.delete(subtask)
    db.commit()
    return {"message": "Subtask deleted successfully"}