from fastapi import APIRouter, Depends, HTTPException, requests,status
from .. import database,models,schemas
from sqlalchemy.orm import Session
from typing import List
from ..auth import get_current_user
import secrets
from datetime import timedelta, datetime,timezone
from app.services.email_service import send_group_invitation
from app.models import InvitationStatus,Role
from app.services.ai_service import create_agents
from app.schemas import AIConversationResponse
from uuid import uuid4

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
    thread_id = request.thread_id
    con=db.query(models.AIConversation).filter(models.AIConversation.thread_id==thread_id,models.AIConversation.user_id==current_user["id"]).first()
    if not con:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,detail="Conversation not found")
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

@router.post("/conversation",response_model=AIConversationResponse)
def get_thread_id(db: Session=Depends(database.get_db),current_user=Depends(get_current_user)):
    thread_id=str(uuid4())
    conv=models.AIConversation(
        thread_id=thread_id,
        user_id=current_user['id'],
        title="new chat",
    )
    db.add(conv)
    db.commit()
    db.refresh(conv)
    return conv

@router.get("/conversation",response_model=list[AIConversationResponse])
def get_all_conversations(db: Session=Depends(database.get_db),current_user=Depends(get_current_user)):
    qur=db.query(models.AIConversation).filter(models.AIConversation.user_id==current_user["id"]).order_by(models.AIConversation.updated_at.desc()).all()
    return qur