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
from app.services.task_planner import build_task_plan
from langgraph.types import interrupt
load_dotenv()

llm=ChatGroq(
    model="openai/gpt-oss-120b",
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
==================================================
20. TASK INTELLIGENCE
==================================================

When the user asks for advice, prioritization, planning,
or recommendations about their work:

1. Retrieve the relevant current tasks using the available tools.

2. Analyze the retrieved tasks using:
   - priority
   - due date
   - completion status
   - overdue status
   - task context/content
   - whether the task is personal or group-related

3. Do not simply repeat the task list.

4. Provide a reasoned recommendation.

5. Clearly distinguish between:
   - facts retrieved from TaskFlow
   - your recommendation or reasoning

6. Never invent deadlines, priorities, or task details.

Examples:

User:
"What should I work on first?"

Retrieve the user's relevant tasks and recommend what should
be done first based on urgency, priority, and status.

User:
"What should I focus on today?"

Retrieve relevant tasks and recommend a practical focus.

User:
"Which task is most urgent?"

Retrieve the current tasks and determine the most urgent one
from the actual task data.

If there is insufficient information to confidently prioritize
the tasks, explain why rather than inventing information.
RESPONSE FORMAT

Never output Markdown tables.

Never use the "|" character for formatting.

Never output literal "\n" characters.

When listing multiple tasks, always use this format:

1. **Task name**
   Priority: HIGH
   Due: August 29, 5:00 PM
   Why: This is the highest-priority task and has the earliest deadline.

2. **Task name**
   Priority: HIGH
   Due: August 29, 6:00 PM
   Why: High priority, but due later.

Use actual newlines between sections.
"""
def get_task_tools(db: Session, user_id: int):

    @tool(args_schema=schemas.Tasks)
    def create_task(title: str, content: str,
                     priority: Priority = Priority.MEDIUM,
    due_date: datetime | None = None
    ,completed: bool = False,estimated_duration: int | None = None):
        """Create a new task for the current user."""

        task = models.tasks(
            title=title,
            content=content,
            priority= priority,
            due_date= due_date,
            completed=completed,
            users_id=user_id,
            estimated_duration=estimated_duration
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
            "completed": task.completed,
            "estimated_duration":task.estimated_duration
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
            "completed": task.completed,
            "estimated_duration":task.estimated_duration
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
            "completed": task.completed,
            "estimated_duration":task.estimated_duration
        }
    @tool
    def delete_task(id: int):
        """Delete the task of a given task id for an authenticated user"""
        qr=db.query(models.tasks).filter(models.tasks.users_id==user_id,models.tasks.id==id).first()
        if not qr:
            return {"error":"Task not found"}
        decision = interrupt({
        "action": "delete_task",
        "task_id": qr.id,
        "task_title": qr.title,
        "message": f"Do you want to delete '{qr.title}'?"
      })
        print("HITL decision received:", repr(decision))
        if decision == "reject":
                     print("Deletion rejected. Task remains:", qr.id, qr.title)
                     return {
                            "status": "rejected",
                            "message": f"Deletion cancelled. '{qr.title}' was not deleted."
                            }
        if decision!="accept":
            return {"status": "rejected","message":f"Task {qr.title} not deleted"}
        print("Approval accepted. Checking task again...")
        task= (
                db.query(models.tasks)
                .filter(
                         models.tasks.users_id == user_id,
                         models.tasks.id == id
                       )
                .first()
        )
        if not task:
            return {"error":"task not found"}
        print("Task found:", task.id, task.title)
        try:
               db.delete(task)
               db.commit()
               print("Database commit successful")
        except Exception as e:
            db.rollback()
            print("Database deletion failed:", repr(e))
            return {"error": "Database deletion failed"}
        return {"status":"deleted","message":f"Task {task.title} deleted successfully"}
    @tool(args_schema=schemas.TasksPost)
    def update_tasks(id: int,title: str | None=None,content: str | None=None, completed:bool | None=None,priority: Priority | None = None,
    due_date: datetime | None = None,estimated_duration: int | None = None):
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
        if estimated_duration is not None:
            qr1.estimated_duration=estimated_duration      
        
        db.commit()
        db.refresh(qr1)
        return {
        "id": qr1.id,
        "title": qr1.title,
        "content": qr1.content,
        "priority":qr1.priority,
        "due_date":qr1.due_date,
        "completed": qr1.completed,
        "estimated_duration":qr1.estimated_duration
    }
    @tool
    def get_datetime():
        """Get the current date and time. Use this when the user mentions relative dates or times such as today, tomorrow, tonight, next week, or Monday."""
        now=datetime.now()
        return {"current_datetime":now.isoformat()}
    @tool
    def plan_my_tasks():
        """Analyze the current user's incomplete personal tasks and
        return a prioritized list based on priority and due dates.
        Use this when the user asks what to work on first, what to
        focus on, or how to prioritize personal tasks"""
        tasks = (
            db.query(models.tasks)
            .filter(models.tasks.users_id == user_id)
            .all()
        )

        task_data = [
            {
                "id": task.id,
                "title": task.title,
                "content": task.content,
                "priority": task.priority,
                "due_date": task.due_date,
                "completed": task.completed,
                "estimated_duration":task.estimated_duration
            }
            for task in tasks
        ]

        return build_task_plan(task_data)

    return [create_task, get_tasks,get_task,delete_task,update_tasks,get_datetime,plan_my_tasks]
    

def create_agents(db:Session,user_id:int):
    tools = get_task_tools(db, user_id)
    agent=create_agent(
        model=llm,
        tools=tools,
        system_prompt=sys,
        checkpointer=checkpointer
    )
    return agent
