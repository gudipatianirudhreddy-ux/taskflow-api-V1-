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
    
@router.get("/invitations/{token}/preview", status_code=status.HTTP_200_OK)
def get_invitation_preview(token: str, db: Session = Depends(database.get_db)):
    """Public preview endpoint: returns group and inviter details for preview before accepting."""
    invitation = db.query(models.GroupInvitation).filter(
        models.GroupInvitation.token == token
    ).first()
    if not invitation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invitation not found")
    expires_at = invitation.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if invitation.status != InvitationStatus.pending or expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=status.HTTP_410_GONE, detail="Invitation is no longer pending or has expired")

    group = db.query(models.Groups).filter(models.Groups.id == invitation.group_id).first()
    inviter = db.query(models.Users).filter(models.Users.id == invitation.invited_by).first()

    return {
        "group_id": invitation.group_id,
        "group_name": group.name if group else "Project",
        "group_description": group.description if group else "",
        "inviter_email": inviter.email if inviter else "",
        "inviter_name": inviter.username if inviter else "",
        "expires_at": expires_at.isoformat()
    }


@router.get("/invitations/{token}", response_class=HTMLResponse, include_in_schema=False)
def invitation_landing(token: str, request: Request, db: Session = Depends(database.get_db)):
    """
    Platform-aware invitation landing page:
    - Android: routes to custom URI scheme multido://groups/invitations/{token}
    - Desktop / Flutter Web: routes to Flutter Web route /groups/invitations/{token}
    """
    invitation = db.query(models.GroupInvitation).filter(
        models.GroupInvitation.token == token
    ).first()
    if not invitation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invitation not found")
    expires_at = invitation.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if invitation.status != InvitationStatus.pending or expires_at < datetime.now(timezone.utc):
        return HTMLResponse(
            "<h2>This invitation is no longer available or has expired.</h2>",
            status_code=status.HTTP_410_GONE,
        )

    group = db.query(models.Groups).filter(models.Groups.id == invitation.group_id).first()
    group_name = escape(group.name if group else "Project")
    group_desc = escape(group.description or "" if group else "")

    frontend_base = os.getenv("FRONTEND_URL", "http://localhost:3000").rstrip("/")
    web_route = f"/groups/invitations/{token}"
    web_url = f"{frontend_base}{web_route}"
    android_deep_link = f"multido://groups/invitations/{token}"

    user_agent = request.headers.get("user-agent", "").lower() if request else ""
    is_android = "android" in user_agent

    primary_url = android_deep_link if is_android else web_url
    primary_label = "Open in MultiDo Pulse (Android)" if is_android else "Open in MultiDo Pulse (Web)"
    secondary_url = web_url if is_android else android_deep_link
    secondary_label = "Or open in Web Browser" if is_android else "Or open in Android App"

    safe_primary_url = escape(primary_url, quote=True)
    safe_secondary_url = escape(secondary_url, quote=True)
    safe_token = escape(token, quote=True)

    return HTMLResponse(f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Join {group_name} — MultiDo Pulse</title>
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #0f1923; color: #e2e8f0; margin: 0; padding: 40px 20px; display: flex; justify-content: center; align-items: center; min-height: 80vh; }}
  .card {{ background: rgba(255,255,255,0.06); border: 1px solid rgba(255,255,255,0.12); border-radius: 16px; padding: 36px 28px; max-width: 480px; width: 100%; text-align: center; box-shadow: 0 8px 32px rgba(0,0,0,0.3); }}
  h2 {{ color: #ffffff; margin-top: 0; font-size: 24px; }}
  p {{ color: #94a3b8; font-size: 15px; line-height: 1.5; }}
  .project-badge {{ display: inline-block; background: rgba(12,237,132,0.15); color: #0CED84; border: 1px solid rgba(12,237,132,0.3); padding: 6px 14px; border-radius: 20px; font-weight: 600; margin-bottom: 16px; }}
  .btn {{ display: inline-block; padding: 14px 28px; background: #0CED84; color: #003318 !important; text-decoration: none; border-radius: 10px; font-weight: 700; font-size: 16px; margin: 16px 0 8px; transition: transform 0.15s; }}
  .btn:hover {{ transform: scale(1.02); }}
  .secondary-link {{ color: #0CED84; font-size: 13px; text-decoration: underline; cursor: pointer; display: inline-block; margin-top: 8px; }}
  .dev-bar {{ margin-top: 24px; padding-top: 16px; border-top: 1px solid rgba(255,255,255,0.1); font-size: 12px; color: #64748b; }}
  .dev-bar input {{ background: #1e293b; border: 1px solid #334155; color: #cbd5e1; padding: 4px 8px; border-radius: 4px; width: 140px; font-size: 12px; }}
  .dev-bar button {{ background: #334155; color: #f8fafc; border: none; padding: 4px 8px; border-radius: 4px; cursor: pointer; font-size: 12px; }}
</style>
<script>
  (function() {{
    const token = "{safe_token}";
    const isAndroid = /Android/i.test(navigator.userAgent);
    const params = new URLSearchParams(window.location.search);
    let webBase = params.get("web_url") || "{frontend_base}";

    if (params.has("port")) {{
      webBase = "http://localhost:" + params.get("port");
    }}

    const webUrl = webBase.replace(/\\/+$/, "") + "/groups/invitations/" + token;
    const androidUrl = "multido://groups/invitations/" + token;

    window.addEventListener("DOMContentLoaded", function() {{
      const mainBtn = document.getElementById("main-btn");
      const altLink = document.getElementById("alt-link");
      const portInput = document.getElementById("port-input");

      if (portInput) {{
        portInput.value = (webBase.match(/:(\\d+)/) || [])[1] || "3000";
      }}

      if (isAndroid) {{
        mainBtn.href = androidUrl;
        mainBtn.textContent = "Open in MultiDo Pulse (Android)";
        altLink.href = webUrl;
        altLink.textContent = "Or open in Web Browser";
      }} else {{
        mainBtn.href = webUrl;
        mainBtn.textContent = "Open in MultiDo Pulse (Web)";
        altLink.href = androidUrl;
        altLink.textContent = "Or open in Android App";

        if (params.get("auto") === "1" || window.location.hostname === "localhost") {{
          setTimeout(function() {{ window.location.href = webUrl; }}, 800);
        }}
      }}
    }});

    window.applyPort = function() {{
      const p = document.getElementById("port-input").value.trim();
      const newWebUrl = "http://localhost:" + p + "/groups/invitations/" + token;
      window.location.href = newWebUrl;
    }};
  }})();
</script>
</head>
<body>
<div class="card">
  <div class="project-badge">Project Invitation</div>
  <h2>Join {group_name}</h2>
  <p>{group_desc if group_desc else "You have been invited to collaborate on this project in MultiDo Pulse."}</p>
  <a id="main-btn" href="{safe_primary_url}" class="btn">{primary_label}</a>
  <br>
  <a id="alt-link" href="{safe_secondary_url}" class="secondary-link">{secondary_label}</a>
  <div class="dev-bar">
    <span>Local dev: </span>
    <input id="port-input" type="text" placeholder="port (3000)">
    <button onclick="applyPort()">Open Port</button>
  </div>
</div>
</body></html>""")

@router.post("/invitations/{token}/accept", status_code=status.HTTP_202_ACCEPTED)
@router.get("/invitations/{token}/accept", status_code=status.HTTP_202_ACCEPTED)
def accept_invitation(token: str,db: Session = Depends(database.get_db),current_user= Depends(get_current_user)):
    qr1=db.query(models.GroupInvitation).filter(models.GroupInvitation.token==token).first()
    if not qr1:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    if qr1.status != InvitationStatus.pending:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invitation is no longer pending.")
    expires_at = qr1.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at < datetime.now(timezone.utc):
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