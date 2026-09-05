from datetime import datetime
from app.schemas import Priority
from langchain.tools import tool
from app import models, schemas
from sqlalchemy.orm import Session
def get_group_tools(db: Session, user_id: int,group_id: int):
    @tool
    def get_group_info():
        """Get the group information for the current authenticated user."""
        gp=db.query(models.Groups).filter(models.Groups.id==group_id).first()
        return {
            "id": gp.id,
            "name": gp.name,
            "description": gp.description,
            "created_at": gp.created_at,
            "owner_id": gp.owners_id
        }
    @tool
    def get_group_members():
        """Get all group members for the current authenticated user."""
        members=db.query(models.Members).filter(models.Members.group_id==group_id).all()
        return [{
            "id": member.id,
            "user_id": member.user_id,
            "role": member.role,
            "joined_at": member.joined_at
        }
            for member in members
        
        ]
    @tool
    def create_group_tasks(title: str,description: str, assigned_to: int, priority: Priority = Priority.MEDIUM, due_date: datetime | None = None):
        """Create a new task for a member of the current group."""
        group=db.query(models.Groups).filter(models.Groups.id==group_id).first()
        if not group:
            return {"error":"group not found"}
        members=db.query(models.Members).filter(models.Members.user_id==user_id,models.Members.group_id==group_id).first()
        if not members:
            return {"error":"You are not member of this group"}
        if group.owners_id!=user_id:
            return {"error":"Only owner can create tasks"}
        assigned=db.query(models.Members).filter(models.Members.group_id==group_id,models.Members.user_id==assigned_to).first()
        if not assigned:
            return {"error":"Assigned user is not a member of this group"}
        tasks=models.GroupTask(
           title=title,
           description=description,
           group_id=group_id,
           assigned_to=assigned_to,
           priority=priority,
           due_date=due_date,
           created_by=user_id,
           completed=False
        )
        db.add(tasks)
        db.commit()
        db.refresh(tasks)
        return {
            "id":tasks.id,
            "title":tasks.title,
            "description":tasks.description,
            "completed":tasks.completed,
            "group_id":tasks.group_id,
            "created_by":tasks.created_by,
            "priority":tasks.priority,
            "due_date":tasks.due_date,
            "assigned_to":tasks.assigned_to
        }
    @tool
    def get_group_tasks():
        """Get the tasks for a particular group"""
        mem=db.query(models.Members).filter(models.Members.group_id==group_id,models.Members.user_id==user_id).first()
        if not mem:
            return {"error":"Member does not exists in this group"}
        tasks=db.query(models.GroupTask).filter(models.GroupTask.group_id==group_id).all()
        return [{
            "task_id":task.id,
            "title":task.title,
            "description":task.description,
            "completed":task.completed,
            "assigned_to":task.assigned_to,
            "due_date":task.due_date,
            "created_by":task.created_by
        } for task in tasks]
    @tool
    def update_group_task(
        task_id: int,
        title: str | None = None,
        description: str | None = None,
        assigned_to: int | None = None,
        priority: Priority | None = None,
        due_date: datetime | None = None,
        completed: bool | None = None
    ):
        """Update a task belonging to the current group."""

        
        mem = db.query(models.Members).filter(
            models.Members.group_id == group_id,
            models.Members.user_id == user_id
        ).first()

        if not mem:
            return {"error": "You are not a member of this group"}

        
        group = db.query(models.Groups).filter(
            models.Groups.id == group_id
        ).first()

        if not group:
            return {"error": "Group not found"}

        if group.owners_id != user_id:
            return {"error": "Only owner can update group tasks"}

        
        task = db.query(models.GroupTask).filter(
            models.GroupTask.id == task_id,
            models.GroupTask.group_id == group_id
        ).first()

        if not task:
            return {"error": "Task not found in this group"}

       
        if assigned_to is not None:
            assigned = db.query(models.Members).filter(
                models.Members.group_id == group_id,
                models.Members.user_id == assigned_to
            ).first()

            if not assigned:
                return {"error": "Assigned user is not a member of this group"}

            task.assigned_to = assigned_to

       
        if title is not None:
            task.title = title

        if description is not None:
            task.description = description

        if priority is not None:
            task.priority = priority

        if due_date is not None:
            task.due_date = due_date

        if completed is not None:
            task.completed = completed

        db.commit()
        db.refresh(task)

        return {
            "id": task.id,
            "title": task.title,
            "description": task.description,
            "completed": task.completed,
            "assigned_to": task.assigned_to,
            "priority": task.priority,
            "due_date": task.due_date,
            "group_id": task.group_id,
            "created_by": task.created_by
        }
    @tool
    def delete_group_task(task_id: int):
        """Delete a task belonging to the current group."""
        mem = db.query(models.Members).filter(
            models.Members.group_id == group_id,
            models.Members.user_id == user_id
        ).first()

        if not mem:
            return {"error": "You are not a member of this group"}

        group = db.query(models.Groups).filter(
            models.Groups.id == group_id
        ).first()

        if not group:
            return {"error": "Group not found"}

        if group.owners_id != user_id:
            return {"error": "Only owner can delete group tasks"}

        task = db.query(models.GroupTask).filter(
            models.GroupTask.id == task_id,
            models.GroupTask.group_id == group_id
        ).first()

        if not task:
            return {"error": "Task not found in this group"}

        db.delete(task)
        db.commit()

        return {"message": "Task deleted successfully"}
    @tool
    def delete_group():
        """Delete the group if the current user is the owner."""
        group = db.query(models.Groups).filter(
            models.Groups.id == group_id
        ).first()

        if not group:
            return {"error": "Group not found"}

        if group.owners_id != user_id:
            return {"error": "Only owner can delete the group"}

        db.delete(group)
        db.commit()

        return {"message": "Group deleted successfully"}
    

    return [get_group_info, get_group_members, create_group_tasks, get_group_tasks, update_group_task, delete_group_task, delete_group]
