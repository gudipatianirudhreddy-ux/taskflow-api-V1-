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
from app.services.group_ai_service import get_graph
from langchain_core.messages import HumanMessage,SystemMessage,AIMessage
from langgraph.types import Command
router=APIRouter(
    prefix='/ai',
    tags=['Ai_Features']
)

@router.post("/chat")
def get_all_tasks( request: schemas.AIChatRequest,db: Session = Depends(database.get_db),current_user= Depends(get_current_user)):
    # tasks=db.query(models.tasks).filter(models.tasks.users_id==current_user["id"])
    # agent=create_agents(
    #     db=db,
    #     user_id=current_user["id"]
    #     )
    thread_id = request.thread_id
    con=db.query(models.AIConversation).filter(models.AIConversation.thread_id==thread_id,models.AIConversation.user_id==current_user["id"]).first()
    if not con:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,detail="Conversation not found")
    graph=get_graph(db,current_user["id"])
    config = {
    "configurable": {
        "thread_id": thread_id
           }
      }
    # result=graph.invoke(
    #           {
    #         "messages":[
    #             HumanMessage(content=request.message)
    #         ]
    #        },
    #     config={
    #         "configurable":{
    #             "thread_id":request.thread_id
    #         }
    #     }

    # )
    if request.decision is not None:
        snapshot = graph.get_state(config)
        interrupts = snapshot.interrupts
        pending_deletion = any(
            getattr(item, "value", {}).get("action") == "delete_task"
            for item in interrupts
        )
        if not pending_deletion:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No pending task deletion approval for this conversation.",
            )
        result = graph.invoke(
            Command(resume=request.decision),
            config=config,
        )
    else:
        if not request.message or not request.message.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A message is required for a normal chat request.",
            )

        result = graph.invoke(
            {"messages": [HumanMessage(content=request.message)]},
            config=config,
        )

    # 4. If the graph paused, return the approval details.
    pending = result.get("__interrupt__", [])

    if pending:
        approval = getattr(pending[0], "value", pending[0])
        return {
            "status": "pending_approval",
            "approval": approval,
        }

    # 5. Otherwise, return the assistant's response.
    for message in reversed(result["messages"]):
        if isinstance(message, AIMessage) and message.content:
            return {
                "status": "completed",
                "message": message.content,
            }

    return {
        "status": "completed",
        "message": "The operation finished, but no assistant response was returned.",
    }
    # user_id=current_user["id"]
    # final_response = result["messages"][-1].content

    # return {"message": final_response}

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

