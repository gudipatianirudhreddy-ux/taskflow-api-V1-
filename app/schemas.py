from pydantic import BaseModel, ConfigDict,EmailStr,constr
from typing import Optional,Literal 
from datetime import datetime
from app.models import InvitationStatus, Role
from app.models import Priority
class Tasks(BaseModel):
    title: str
    content: str
    completed: bool=False
    priority: Priority=Priority.MEDIUM
    due_date: datetime |None=None
    estimated_duration: int | None = None
    

class TasksCreate(Tasks):
    pass
class TasksPost(BaseModel):
    id: int
    title: str | None = None
    content: str | None = None
    completed: bool | None = None
    priority: Priority | None = None
    due_date: datetime | None = None
    estimated_duration: int | None = None
    class Config:
        from_attributes=True

class UserCreate(BaseModel):
    username: str
    email: EmailStr
    password: constr(min_length=8, max_length=72)

class UserPost(BaseModel):
     id: int
     email: EmailStr
     class Config:
         from_attributes=True
class Token(BaseModel):
    access_token: str
    token_type: str
    
class Group(BaseModel):
    name: str
    description: str

class GroupPost(Group):
    id:int 
    class Config:
             from_attributes=True
             
class UpdateGroup(BaseModel):
    name: Optional[str]=None
    description: Optional[str]=None
    
class GroupInvitationBase(BaseModel):
    email: EmailStr

class GroupInvitationCreate(GroupInvitationBase):
    
    expires_at: datetime

class GroupInvitationResponse(GroupInvitationBase):
    id: int
    invited_by: int
    token: str
    status: InvitationStatus
    expires_at: datetime
    created_at: datetime

    class Config:
        from_attributes = True

class GroupMemberResponse(BaseModel):
    id: int
    username: str
    email: EmailStr
    role: Role
    joined_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class MessageResponse(BaseModel):
    message: str

class GroupTasksCreate(BaseModel):
    title: str
    description:  Optional[str]=None
    priority: Priority | None = None
    due_date: datetime | None = None
    completed: bool | None = None
    assigned_to: int
    

class GroupTaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    completed: Optional[bool] = None
    assigned_to: Optional[int] = None
    due_date: Optional[datetime] = None
    priority: Optional[Priority] = None

class GroupTaskResponse(BaseModel):
    id: int
    title: str
    description: Optional[str]
    completed: bool
    group_id: int
    assigned_to: int
    created_by: int
    priority: Priority | None = None
    due_date: datetime| None=None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class RefreshTokenRequest(BaseModel):
    refresh_token: str

class AIChatRequest(BaseModel):
    thread_id: str
    message: str |None=None
    decision: Literal["accept","reject"] | None = None
    
    
class MessageResponse(BaseModel):
    message: str
    class Config:
        from_attributes =True
class AIConversationResponse(BaseModel):
    thread_id: str
    title: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

class SubtaskCreate(BaseModel):
    title: str
    content: str | None = None
    completed: bool = False
    due_date: datetime | None = None

class SubtaskUpdate(BaseModel):
    title: str | None = None
    content: str | None = None
    completed: bool | None = None
    due_date: datetime | None = None


class SubtaskResponse(BaseModel):
    id: int
    title: str
    content: str | None
    completed: bool
    due_date: datetime | None
    task_id: int

    class Config:
        from_attributes = True

class GroupSubtaskCreate(BaseModel):
    title: str
    description: str | None = None
    group_task_id: Optional[int] = None
    completed: bool = False
    due_date: datetime | None = None


class GroupSubtaskResponse(BaseModel):
    id: int
    title: str
    description: str | None
    completed: bool
    group_task_id: int
    due_date: datetime | None
    

    class Config:
        from_attributes = True

class GroupSubtaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    completed: Optional[bool] = None
    due_date: datetime| None=None
