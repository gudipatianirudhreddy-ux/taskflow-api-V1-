from pydantic import BaseModel, ConfigDict, EmailStr, constr, Field, field_validator, field_serializer
from typing import Optional,Literal 
from datetime import datetime
from app.models import InvitationStatus, Role
from app.models import Priority
from app.date_utils import normalize_due_date_input, format_stored_due_date


class DueDateInputModel(BaseModel):
    """Normalize incoming due dates to naive UTC for existing DB columns."""

    @field_validator("due_date", mode="before", check_fields=False)
    @classmethod
    def parse_due_date(cls, value):
        return normalize_due_date_input(value)


class DueDateResponseModel(BaseModel):
    """Serialize stored UTC datetimes with an explicit Z suffix."""

    @field_serializer("due_date", when_used="json", check_fields=False)
    def serialize_due_date(self, value):
        return format_stored_due_date(value)


class Tasks(DueDateInputModel):
    title: str
    content: str
    completed: bool=False
    priority: Priority=Priority.MEDIUM
    due_date: datetime |None=None
    estimated_duration: int | None = None
    

class TasksCreate(Tasks):
    pass
class TasksPost(DueDateResponseModel):
    id: int
    title: str | None = None
    content: str | None = None
    completed: bool | None = None
    priority: Priority | None = None
    due_date: datetime | None = None
    estimated_duration: int | None = None
    class Config:
        from_attributes=True

class AgentTaskCreateArgs(BaseModel):
    """Arguments for the AI personal-task creation tool."""
    title: str
    content: str
    completed: bool = False
    priority: Priority = Priority.MEDIUM
    due_date: str | None = Field(default=None, description="ISO date YYYY-MM-DD or ISO datetime; never pass natural-language phrases.")
    estimated_duration: int | None = None


class AgentTaskUpdateArgs(BaseModel):
    """Arguments for the AI personal-task update tool.

    Provide due_date as an ISO date/time string. Set clear_due_date=True to
    remove an existing deadline; do not set both fields at once.
    """
    id: int
    title: str | None = None
    content: str | None = None
    completed: bool | None = None
    priority: Priority | None = None
    due_date: str | None = Field(default=None, description="ISO date YYYY-MM-DD or ISO datetime; never pass natural-language phrases.")
    estimated_duration: int | None = None
    clear_due_date: bool = Field(default=False, description="Set true only when the user explicitly asks to remove the current deadline.")


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

class GroupTasksCreate(DueDateInputModel):
    title: str
    description:  Optional[str]=None
    priority: Priority | None = None
    due_date: datetime | None = None
    completed: bool | None = None
    assigned_to: int
    

class GroupTaskUpdate(DueDateInputModel):
    title: Optional[str] = None
    description: Optional[str] = None
    completed: Optional[bool] = None
    assigned_to: Optional[int] = None
    due_date: Optional[datetime] = None
    priority: Optional[Priority] = None

class GroupTaskResponse(DueDateResponseModel):
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

class SubtaskCreate(DueDateInputModel):
    title: str
    content: str | None = None
    completed: bool = False
    due_date: datetime | None = None

class SubtaskUpdate(DueDateInputModel):
    title: str | None = None
    content: str | None = None
    completed: bool | None = None
    due_date: datetime | None = None


class SubtaskResponse(DueDateResponseModel):
    id: int
    title: str
    content: str | None
    completed: bool
    due_date: datetime | None
    task_id: int

    class Config:
        from_attributes = True

class GroupSubtaskCreate(DueDateInputModel):
    title: str
    description: str | None = None
    group_task_id: Optional[int] = None
    completed: bool = False
    due_date: datetime | None = None


class GroupSubtaskResponse(DueDateResponseModel):
    id: int
    title: str
    description: str | None
    completed: bool
    group_task_id: int
    due_date: datetime | None
    

    class Config:
        from_attributes = True

class GroupSubtaskUpdate(DueDateInputModel):
    title: Optional[str] = None
    description: Optional[str] = None
    completed: Optional[bool] = None
    due_date: datetime| None=None
