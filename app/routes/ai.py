from fastapi import APIRouter, Depends, HTTPException,status
from .. import database,models,schemas
from sqlalchemy.orm import Session
from typing import List
from ..auth import get_current_user
import secrets
from datetime import timedelta, datetime,timezone
from app.services.email_service import send_group_invitation
from app.models import InvitationStatus,Role
from app.services.ai_service import create_agents

router=APIRouter(
    prefix='/ai',
    tags=['Ai_Features']
)

@router.post("/chat")
def get_all_tasks( request: schemas.AIChatRequest,db: Session = Depends(database.get_db),current_user= Depends(get_current_user)):
    # tasks=db.query(models.tasks).filter(models.tasks.users_id==current_user["id"])
    agent=create_agents(
        db=db,
        user_id=current_user["id"]
        )
    thread_id = f"taskapi-user-{current_user["id"]}"
    response=agent.invoke(
        {
            "messages":[
                {"role":"user",
                 "content":request.message
                }
            ]
        },
        config={
            "configurable":{
                "thread_id":thread_id
            }
        }
    )
    final_response = response["messages"][-1].content

    return {"message": final_response}


