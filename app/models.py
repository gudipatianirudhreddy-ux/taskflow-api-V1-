from sqlalchemy import Column,BigInteger,String,Boolean,DateTime, text,ForeignKey,UniqueConstraint, Enum
from sqlalchemy.orm import relationship
from . database import Base
from sqlalchemy.sql import func
# from sqlalchemy.ext.declarative import declarative_base

import enum

class InvitationStatus(str, enum.Enum):
    pending = "pending"
    accepted = "accepted"
    expired = "expired"

class Role(str, enum.Enum):
    member="member"
    admin="admin"
    owner="owner"

class Priority(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"

# Base=declarative_base()
# metadata=Base.metadata
class tasks(Base):
    __tablename__="Tasks"
    id=Column(BigInteger, primary_key=True, nullable=False)
    title=Column(String, nullable=False)
    content=Column(String, nullable=False)
    priority= Column(Enum(Priority),nullable=False,default=Priority.MEDIUM,server_default="medium")
    due_date=Column(DateTime,nullable=True)
    completed=Column(Boolean, nullable=False, server_default="False")
    created_at=Column(DateTime(timezone=True),nullable=False, server_default=text('now()'))

    updated_at=Column(DateTime(timezone=True),server_default=func.now(),onupdate=func.now())
    users_id=Column(BigInteger,ForeignKey("users.id", ondelete='CASCADE'))
    
class Users(Base):
    __tablename__="users"
    id=Column(BigInteger, primary_key=True, nullable=False)
    username=Column(String, nullable=False)
    email=Column(String,nullable=False,unique=True)
    google_id=Column(String,nullable=False,unique=True)
    created_at=Column(DateTime(timezone=True), nullable=False, server_default=text('now()'))

class Groups(Base):
    __tablename__="Group"
    id=Column(BigInteger, primary_key=True, nullable=False)
    name=Column(String, nullable=False)
    description=Column(String, nullable=False)
    created_at=Column(DateTime(timezone=True),nullable=False,server_default=text('now()'))
    updated_at=Column(DateTime(timezone=True),server_default=func.now(),onupdate=func.now())
    owners_id=Column(BigInteger,ForeignKey("users.id", ondelete='CASCADE'))

class Members(Base):
    __tablename__="GroupMembers"
    __table_args__ = (
        UniqueConstraint(
            "group_id",
            "user_id",
            name="uq_group_member"
        ),
    )
    id=Column(BigInteger,primary_key=True,nullable=False)
    group_id=Column(BigInteger,ForeignKey("Group.id", ondelete='CASCADE'))
    user_id=Column(BigInteger,ForeignKey("users.id", ondelete='CASCADE')) 
    role=Column(Enum(Role), nullable=False, default=Role.member.value)
    joined_at=Column(DateTime(timezone=True), server_default=text('now()'))
       
class GroupInvitation(Base):
    __tablename__ = "group_invitations"

    id = Column(BigInteger, primary_key=True, nullable=False)
    group_id = Column(BigInteger, ForeignKey("Group.id", ondelete="CASCADE"), nullable=False)
    email = Column(String(255), nullable=False)
    invited_by = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    token = Column(String(255), unique=True, nullable=False)
    status = Column(Enum(InvitationStatus), nullable=False, default=InvitationStatus.pending.value)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=text("now()"))
    group = relationship("Groups", backref="invitations")
    inviter = relationship("Users", foreign_keys=[invited_by], backref="sent_invitations")

class GroupTask(Base):
    __tablename__ = "group_tasks"

    id = Column(BigInteger, primary_key=True, index=True)

    title = Column(String, nullable=False)
    description = Column(String, nullable=True)

    completed = Column(Boolean, server_default="False")

    group_id = Column(
        BigInteger,
        ForeignKey("Group.id", ondelete="CASCADE"),
        nullable=False
    )

    assigned_to = Column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False
    )

    created_by = Column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False
    )

    created_at = Column(
        DateTime(timezone=True),
        server_default=text("now()")
    )

    updated_at = Column(
        DateTime(timezone=True),
        server_default=text("now()"),
        onupdate=func.now()
    )
    

