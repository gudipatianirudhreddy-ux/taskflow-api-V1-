import os
from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain_groq import ChatGroq
from app import models, schemas
from sqlalchemy.orm import Session
from langchain.tools import tool
from datetime import datetime
from app.models import Priority
from app.services.checkpoint import checkpointer
load_dotenv()

llm=ChatGroq(
    model="openai/gpt-oss-20b",
    temperature=0.7
)
sys = """
You are TaskAPI's intelligent task and group management assistant.

Your purpose is to help authenticated users manage their personal tasks, subtasks, and groups using the available tools.

GENERAL RULES

1. Carefully understand the user's request before taking any action.

2. When a request requires reading, creating, updating, or deleting data, use the appropriate available tool.

3. Never claim that an action was completed unless the corresponding tool was successfully executed successfully.

4. Never invent, guess, or assume information about:
   - tasks
   - subtasks
   - groups
   - group members
   - invitations
   - users
   - database records

   If the required information is unavailable, use an appropriate tool or ask the user for clarification.

5. If essential information is missing and cannot be reasonably inferred, ask a concise clarification question.

6. If multiple actions are required, determine the correct sequence and execute the necessary tools in that order.

7. Base your responses only on:
   - the user's request
   - information returned by tools
   - information available in the conversation

8. If a request cannot be completed using the available tools, clearly explain the limitation. Never pretend that an action was performed.

9. Be concise, helpful, and focused on task and group management.

TASK CREATION

10. When creating a task:
    - title and content should reflect the user's request
    - completed should normally be False unless the user explicitly says otherwise
    - priority should use the user's requested priority
    - if no priority is specified, use MEDIUM
    - due_date is optional and should only be set when the user provides a deadline, date, or time

11. Supported priority levels are:
    - LOW
    - MEDIUM
    - HIGH
    - URGENT

12. Do not invent a due date if the user does not provide one.

DATE AND TIME HANDLING

13. When the user provides a relative date or time such as:
    - today
    - tomorrow
    - tonight
    - next Monday
    - this weekend
    - in 2 days
    - in 3 hours

    use the current date/time tool when necessary to determine the actual date and time.

14. Convert relative dates and times into an appropriate datetime value before passing them to a task creation or update tool.

15. If the user provides a date but no specific time, do not invent an arbitrary time unless your application has a clearly defined default behavior.

16. If the user's requested date or time is ambiguous and clarification is necessary, ask the user.

TASK UPDATES

17. When updating a task, modify only the fields explicitly requested by the user.

18. Do not overwrite existing title, content, completion status, priority, or due date unless the user requested that change.

19. For example:
    - "Make task 5 urgent" should only update priority.
    - "Mark task 3 as completed" should only update completion status.
    - "Change the deadline of task 2" should only update the due date.

TASK RETRIEVAL

20. When the user asks to see tasks, use the appropriate task retrieval tool.

21. Do not claim that a task exists unless it was returned by a tool.

22. When displaying tasks, include relevant information when available:
    - task title
    - completion status
    - priority
    - due date
    - details/content

23. If a task has no due date, indicate:
    Due date: Not set

TASK DISPLAY FORMAT

24. Never use Markdown tables.

25. Never use "|" characters to format task data.

26. Never output literal "\\n" characters.

27. Use actual line breaks.

28. Use a simple numbered list when displaying multiple tasks.

29. Keep each task easy to read.

Example:

Here are your tasks:

1. Finish TaskAPI backend
Status: Not completed
Priority: HIGH
Due date: 2026-08-29 18:00
Details: Complete the remaining backend features

2. Study DSA
Status: Not completed
Priority: MEDIUM
Due date: Not set
Details: Practice array and binary search problems

After successfully completing an action, clearly tell the user what was done.
"""
def get_task_tools(db: Session, user_id: int):

    @tool(args_schema=schemas.Tasks)
    def create_task(title: str, content: str,
                     priority: Priority = Priority.MEDIUM,
    due_date: datetime | None = None
    ,completed: bool = False):
        """Create a new task for the current user."""

        task = models.tasks(
            title=title,
            content=content,
            priority= priority,
            due_date= due_date,
            completed=completed,
            users_id=user_id
        )

        db.add(task)
        db.commit()
        db.refresh(task)

        return {
            "id": task.id,
            "title": task.title,
            "content": task.content,
            "priority":task.priority,
            "due_date":task.due_date,
            "completed": task.completed
        }

    @tool
    def get_tasks():
        """Get all tasks belonging to the current authenticated user."""
        tasks=db.query(models.tasks).filter(models.tasks.users_id==user_id).all()
        return [{
            "id": task.id,
            "title": task.title,
            "content": task.content,
            "priority":task.priority,
            "due_date":task.due_date,
            "completed": task.completed
        }
            for task in tasks
        
        ]
    @tool
    def get_task(id: int):
        """Get the task by id for an  authenticated user"""
        task=db.query(models.tasks).filter(models.tasks.id==id,models.tasks.users_id==user_id).first()
        if not task:
            return {"error": "Task not found"}
        return {
            "id": task.id,
            "title": task.title,
            "content": task.content,
            "priority":task.priority,
             "due_date":task.due_date,
            "completed": task.completed
        }
    @tool
    def delete_task(id: int):
        """Delete the task of a given task id for an authenticated user"""
        qr=db.query(models.tasks).filter(models.tasks.users_id==user_id,models.tasks.id==id).first()
        if not qr:
            return {"error":"Task not found"}
        db.delete(qr)
        db.commit()
        return {"message":"Returned succesfully"}
    @tool(args_schema=schemas.TasksPost)
    def update_tasks(id: int,title: str | None=None,content: str | None=None, completed:bool | None=None,priority: Priority | None = None,
    due_date: datetime | None = None):
        """Update a task using its ID for the current authenticated user."""
        qr1=db.query(models.tasks).filter(models.tasks.users_id==user_id,models.tasks.id==id).first()
        if not qr1:
            return {"error":"Task not found"}
        if title is not None:
             qr1.title = title
        if content is not None:
            qr1.content = content
        if completed is not None:
            qr1.completed = completed
        if priority is not None:
            qr1.priority =priority
        if due_date is not None:
            qr1.due_date=due_date       
        
        db.commit()
        db.refresh(qr1)
        return {
        "id": qr1.id,
        "title": qr1.title,
        "content": qr1.content,
        "priority":qr1.priority,
        "due_date":qr1.due_date,
        "completed": qr1.completed
    }
    @tool
    def get_datetime():
        """Get the current date and time. Use this when the user mentions relative dates or times such as today, tomorrow, tonight, next week, or Monday."""
        now=datetime.now()
        return {"current_datetime":now.isoformat()}
    



        

        
    return [create_task, get_tasks,get_task,delete_task,update_tasks,get_datetime]
    

def create_agents(db:Session,user_id:int):
    tools = get_task_tools(db, user_id)
    agent=create_agent(
        model=llm,
        tools=tools,
        system_prompt=sys,
        checkpointer=checkpointer
    )
    return agent
