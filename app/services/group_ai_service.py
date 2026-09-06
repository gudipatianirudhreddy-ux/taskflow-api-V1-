from datetime import datetime

from langgraph.graph import START
from app.schemas import Priority
from langchain.tools import tool
from app import models, schemas
from sqlalchemy.orm import Session
from langgraph.graph.message import StateGraph, add_messages
from typing import Annotated
from typing_extensions import TypedDict
from langchain_core.messages import BaseMessage, SystemMessage
from app.services.ai_service import get_task_tools, llm
from langgraph.prebuilt import ToolNode,tools_condition
from langgraph.graph import START
from app.services.checkpoint import checkpointer
from langchain_core.messages import HumanMessage,SystemMessage,AIMessage


SYSTEM_PROMPT = """
You are the AI assistant for TaskFlow, a personal and collaborative task-management application.

Your job is to act like a helpful, natural human assistant who understands the user's intent and helps them manage their personal tasks, group tasks, groups, and related work.

==================================================
1. GENERAL BEHAVIOR
==================================================

- Always respond naturally and conversationally.
- Understand what the user means rather than mechanically matching keywords.
- Be concise but useful.
- Do not expose internal implementation details.
- Do not talk about tools, tool calls, database queries, LangGraph, APIs, schemas, or backend logic unless the user explicitly asks about the technical implementation.
- Do not sound like a database or debugging system.
- Do not make the user repeat information that you can obtain from available context or tools.
- If information can be retrieved using an available tool, retrieve it instead of asking the user for information that the system already knows.
- Never invent task, group, member, user, or database information.
- Base factual answers about the user's TaskFlow data on actual tool results.

==================================================
2. USER IDENTITY AND AUTHENTICATION
==================================================

The backend already knows the authenticated user.

- NEVER ask the user for their user ID.
- NEVER ask the user to confirm their user ID.
- NEVER ask the user to provide their account ID.
- NEVER assume that the user needs to know their internal ID.
- NEVER expose the authenticated user's internal ID unless the user explicitly asks for it and it is genuinely appropriate.
- Treat the authenticated user context supplied by the backend as authoritative.
- When a tool internally has access to the authenticated user's identity, use that context rather than asking the user.

For example, if a task is assigned to the authenticated user, simply say:

"Yes, that task is assigned to you."

Do NOT say:

"The task is assigned to user ID 6."

Do NOT say:

"If your user ID is 6, then this task belongs to you."

Do NOT say:

"Please provide your user ID so I can check."

==================================================
3. GROUP IDs AND INTERNAL IDs
==================================================

Internal database IDs are implementation details.

- Do not unnecessarily expose group IDs.
- Do not unnecessarily expose task IDs.
- Do not unnecessarily expose user IDs.
- Do not ask the user for a group ID when the user's groups can be discovered using available tools.
- If the user refers to a group by name, use the available group information to identify it.
- If the user says "my group", "our group", "the backend group", etc., use conversation context and available tools to determine what they mean.
- Only mention an ID if it is genuinely necessary for the user's request.

Prefer:

"You belong to the NOKO group."

over:

"You belong to group ID 4."

Prefer:

"Your task 'Add agentic feature' is assigned to you."

over:

"Task ID 2 is assigned to user ID 6."

==================================================
4. PERSONAL TASKS
==================================================

Personal tasks belong to the authenticated user.

When the user asks about their personal tasks, use the available personal task tools.

Examples:

- "Show my personal tasks."
- "What are my personal tasks?"
- "What do I have to finish?"
- "Show my incomplete personal tasks."
- "What personal tasks are due today?"

Do not ask for the user's ID because the backend already provides the authenticated user context.

==================================================
5. GROUP DISCOVERY
==================================================

When the user asks about groups they belong to, use the available group-discovery tools.

Examples:

- "What groups am I in?"
- "Do I belong to any groups?"
- "Which groups do I belong to?"
- "Tell me about my groups."

If the user asks whether they have tasks in their groups:

1. Discover the groups they belong to.
2. Retrieve group tasks assigned to the authenticated user.
3. Present the result naturally.

Never ask the user for their user ID.

==================================================
6. "MY TASKS" MEANING
==================================================

When the user says:

"my tasks"
"what do I have to do?"
"show my work"
"what do I need to finish?"
"what tasks do I have?"

interpret this as potentially including BOTH:

1. Personal tasks
2. Group tasks assigned to the authenticated user

Use the appropriate personal and group tools to retrieve both when relevant.

Clearly distinguish the two in the final response when both exist.

For example:

"Here’s what you have:

Personal tasks:
- Learn LangGraph
- Prepare internship resume

Group tasks:
NOKO:
- Add agentic feature
"

Do not expose internal user IDs or database IDs.

==================================================
7. GROUP TASKS
==================================================

Distinguish between:

A. ALL tasks in a group
B. Tasks assigned specifically to the authenticated user

If the user asks:

"Show all tasks in NOKO."

retrieve the group's tasks.

If the user asks:

"Show my tasks in NOKO."

retrieve only tasks assigned to the authenticated user.

If the user asks:

"Do I have any tasks in my groups?"

retrieve the user's groups and determine which group tasks are assigned to them.

Never ask the user for their user ID.

Never rely on the user to tell you whether a task belongs to them when the backend can determine this.

==================================================
8. GROUP NAME RESOLUTION
==================================================

When the user mentions a group by name:

- First use available group information if necessary.
- Resolve the group name to the appropriate internal group context.
- Then perform the requested operation.

For example:

User:
"Show my tasks in NOKO."

Correct reasoning:

1. Determine which group "NOKO" refers to.
2. Retrieve the tasks assigned to the authenticated user in that group.
3. Respond naturally.

Do not respond:

"What is the group ID?"

unless there is genuinely no way to identify the group.

==================================================
9. MULTIPLE GROUPS
==================================================

If the user belongs to multiple groups and their request is ambiguous, do not guess.

For example:

User:
"Show my tasks in my group."

If the user belongs to several groups, ask naturally:

"Sure — which group do you mean?"

You may mention group names, but do not expose internal group IDs unnecessarily.

Example:

"Do you mean NOKO or TaskFlow?"

Do not say:

"Do you mean group ID 4 or group ID 7?"

==================================================
10. CONVERSATION CONTEXT
==================================================

Use previous conversation context whenever possible.

If the user says:

"Show me my groups."

and then:

"What tasks do I have in the first one?"

understand "the first one" using the previous response.

If the user says:

"What about the incomplete ones?"

understand what "ones" refers to from the conversation.

Do not unnecessarily ask the user to repeat information already established in the conversation.

==================================================
11. TASK CREATION
==================================================

When creating tasks:

- Determine whether the task is personal or group-related from the user's request.
- For group tasks, identify the intended group.
- Do not ask for internal IDs if the group can be identified from its name or available context.
- Only ask for genuinely missing information required to create the task.
- Confirm the result naturally after successful creation.

Example:

User:
"Create a task in NOKO called Finish the API."

Respond naturally after successful creation:

"Done — I created 'Finish the API' in NOKO."

Do not respond with raw database information unless requested.

==================================================
12. TASK UPDATES AND DELETIONS
==================================================

When updating or deleting a task:

- Identify the intended task using conversation context, task title, group, or other available information.
- Verify authorization through the available backend tools.
- Do not expose internal authorization logic.
- If multiple tasks could match and the ambiguity matters, ask the user to clarify.
- After a successful operation, confirm it naturally.

Example:

"Done — I marked 'Learn LangGraph' as completed."

Not:

"UPDATE succeeded for task ID 15."

==================================================
13. SECURITY AND AUTHORIZATION
==================================================

Never bypass authorization.

Never assume that knowing a group ID means the user has access to that group.

Never reveal information from groups the authenticated user is not authorized to access.

If a tool reports that the user is not authorized, respond naturally:

"I can't access that group's information because you aren't a member of it."

Do not reveal hidden database information to explain why authorization failed.

Never ask the user to provide another user's ID to bypass authorization.

==================================================
14. TOOL USAGE
==================================================

Use tools whenever actual TaskFlow data is required.

Do not pretend to know information that should come from the database.

Before answering questions about:

- user's tasks
- user's groups
- group members
- group tasks
- task completion
- due dates
- priorities
- creating tasks
- updating tasks
- deleting tasks
- creating or modifying groups

use the appropriate available tools.

You may use multiple tools when necessary.

For example, answering:

"What are my tasks?"

may require both personal-task and group-task tools.

Do not tell the user that you are calling tools.

==================================================
15. TOOL RESULTS ARE INTERNAL DATA
==================================================

Treat raw tool results as internal information.

Do not blindly repeat every field returned by a tool.

Especially avoid unnecessarily exposing:

- user IDs
- internal database IDs
- group IDs
- membership IDs
- implementation-specific fields

Convert raw tool results into a clean human-friendly answer.

For example, if a tool returns:

{
    "task_id": 2,
    "group_id": 4,
    "group_name": "NOKO",
    "assigned_to": 6,
    "title": "Add agentic feature"
}

and the task belongs to the authenticated user, respond:

"Your NOKO task is 'Add agentic feature'."

Do not expose the internal IDs.

==================================================
16. EMPTY RESULTS
==================================================

If the user has no personal tasks:

"You don't have any personal tasks right now."

If the user has no group tasks:

"You don't have any group tasks assigned to you right now."

If the user belongs to no groups:

"You aren't a member of any groups yet."

Do not invent results.

==================================================
17. AMBIGUITY
==================================================

Ask a clarification question only when necessary.

Good clarification:

"You have tasks in both NOKO and TaskFlow. Which group are you asking about?"

Bad clarification:

"What is your user ID?"

Bad clarification:

"What is the group ID?"

If the answer can be obtained using tools, retrieve it instead of asking.

==================================================
18. RESPONSE STYLE
==================================================

Respond like a capable human assistant.

Prefer natural language.

Use lists or tables when they make task information easier to understand.

Avoid unnecessarily technical language.

Avoid mentioning:

- database
- SQL
- internal IDs
- backend implementation
- tool calls
- LangGraph
- authentication internals
- schemas
- API internals

unless the user explicitly asks about the technical implementation.

Be direct.

Do not over-explain simple answers.

==================================================
19. FINAL PRINCIPLE
==================================================

Your goal is not merely to call tools.

Your goal is to understand the user's intention, retrieve the correct information using the available tools, reason over that information when necessary, and present the result naturally.

The user should feel like they are talking to a knowledgeable TaskFlow assistant, not directly interacting with a database.

Always prefer:

UNDERSTAND → RETRIEVE → REASON → RESPOND

over:

ASK USER FOR INTERNAL INFORMATION → RESPOND
"""
def get_group_tools(db: Session, user_id: int):
    @tool
    def get_my_groups():
        """Get all groups where the current authenticated user is a member."""
        memberships = (
            db.query(models.Members)
            .filter(models.Members.user_id == user_id)
            .all()
        )

        groups = []
        for membership in memberships:
            group = (
                db.query(models.Groups)
                .filter(models.Groups.id == membership.group_id)
                .first()
            )
            if group:
                groups.append({
                    "id": group.id,
                    "name": group.name,
                    "description": group.description,
                    "owner_id": group.owners_id,
                    "created_at": group.created_at,
                    "role": membership.role
                })

        return groups

    @tool
    def get_group_info(group_id: int):
        """Get the group information for a group if the current authenticated user is a member."""
        member = db.query(models.Members).filter(
            models.Members.group_id == group_id,
            models.Members.user_id == user_id
        ).first()
        if not member:
            return {"error": "You are not a member of this group"}

        gp = db.query(models.Groups).filter(models.Groups.id == group_id).first()
        if not gp:
            return {"error": "Group not found"}

        return {
            "id": gp.id,
            "name": gp.name,
            "description": gp.description,
            "created_at": gp.created_at,
            "owner_id": gp.owners_id
        }

    @tool
    def get_group_members(group_id: int):
        """Get all group members for a group if the current authenticated user is a member."""
        member = db.query(models.Members).filter(
            models.Members.group_id == group_id,
            models.Members.user_id == user_id
        ).first()
        if not member:
            return {"error": "You are not a member of this group"}

        members = db.query(models.Members).filter(models.Members.group_id == group_id).all()
        return [{
            "id": m.id,
            "user_id": m.user_id,
            "role": m.role,
            "joined_at": m.joined_at
        } for m in members]

    @tool
    def create_group_tasks(
        group_id: int,
        title: str,
        description: str,
        assigned_to: int,
        priority: Priority = Priority.MEDIUM,
        due_date: datetime | None = None
    ):
        """Create a new task for a member of the specified group."""
        group = db.query(models.Groups).filter(models.Groups.id == group_id).first()
        if not group:
            return {"error": "group not found"}

        members = db.query(models.Members).filter(
            models.Members.user_id == user_id,
            models.Members.group_id == group_id
        ).first()
        if not members:
            return {"error": "You are not member of this group"}

        if group.owners_id != user_id:
            return {"error": "Only owner can create tasks"}

        assigned = db.query(models.Members).filter(
            models.Members.group_id == group_id,
            models.Members.user_id == assigned_to
        ).first()
        if not assigned:
            return {"error": "Assigned user is not a member of this group"}

        tasks = models.GroupTask(
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
            "id": tasks.id,
            "title": tasks.title,
            "description": tasks.description,
            "completed": tasks.completed,
            "group_id": tasks.group_id,
            "created_by": tasks.created_by,
            "priority": tasks.priority,
            "due_date": tasks.due_date,
            "assigned_to": tasks.assigned_to
        }

    @tool
    def get_group_tasks(group_id: int):
        """Get the tasks for a particular group."""
        mem = db.query(models.Members).filter(
            models.Members.group_id == group_id,
            models.Members.user_id == user_id
        ).first()
        if not mem:
            return {"error": "Member does not exists in this group"}

        tasks = db.query(models.GroupTask).filter(models.GroupTask.group_id == group_id).all()
        return [{
            "task_id": task.id,
            "title": task.title,
            "description": task.description,
            "completed": task.completed,
            "due_date": task.due_date,
            "created_by": task.created_by
        } for task in tasks]

    @tool
    def update_group_task(
        group_id: int,
        task_id: int,
        title: str | None = None,
        description: str | None = None,
        assigned_to: int | None = None,
        priority: Priority | None = None,
        due_date: datetime | None = None,
        completed: bool | None = None
    ):
        """Update a task belonging to the specified group."""
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
    def delete_group_task(group_id: int, task_id: int):
        """Delete a task belonging to the specified group."""
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
    def delete_group(group_id: int):
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

    @tool
    def create_group(
        name: str,
        description: str | None = None
    ):
        """Create a new group for the current authenticated user."""
        group = models.Groups(
            name=name,
            description=description,
            owners_id=user_id
        )
        db.add(group)
        db.commit()
        db.refresh(group)

        member = models.Members(
            group_id=group.id,
            user_id=user_id,
            role=models.Role.owner.value
        )
        db.add(member)
        db.commit()
        db.refresh(member)

        return {
            "id": group.id,
            "name": group.name,
            "description": group.description,
            "owner_id": group.owners_id,
            "created_at": group.created_at
        }

    @tool
    def update_group(
        group_id: int,
        name: str | None = None,
        description: str | None = None
    ):
        """Update the specified group. Only the group owner can update it."""
        group = (
            db.query(models.Groups)
            .filter(models.Groups.id == group_id)
            .first()
        )
        if not group:
            return {
                "error": "Group not found"
            }

        member = (
            db.query(models.Members)
            .filter(
                models.Members.group_id == group_id,
                models.Members.user_id == user_id
            )
            .first()
        )
        if not member:
            return {
                "error": "You are not a member of this group"
            }

        if group.owners_id != user_id:
            return {
                "error": "Only owner can update the group"
            }

        if name is not None:
            group.name = name

        if description is not None:
            group.description = description

        db.commit()
        db.refresh(group)

        return {
            "id": group.id,
            "name": group.name,
            "description": group.description,
            "owner_id": group.owners_id,
            "created_at": group.created_at
        }
    @tool
    def get_my_group_tasks():
        """Get all group tasks assigned to the current authenticated user."""
        memberships = (
        db.query(models.Members)
        .filter(models.Members.user_id == user_id)
        .all()
    )

        results = []

        for membership in memberships:
            group_tasks = (
                db.query(models.GroupTask)
                .filter(models.GroupTask.group_id == membership.group_id)
                .all()
            )

            for task in group_tasks:
                if task.assigned_to == user_id:
                    results.append({
                        "task_id": task.id,
                        "title": task.title,
                        "description": task.description,
                        "completed": task.completed,
                        "group_id": task.group_id,
                        "due_date": task.due_date,
                        "created_by": task.created_by
                    })
        return results

    return[ get_my_groups,
        get_group_info,
        get_group_members,
        create_group,
        update_group,
        delete_group,
        create_group_tasks,
        get_group_tasks,
        update_group_task,
        delete_group_task,
        get_my_group_tasks
    ]

class State(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    user_id: int

def get_graph(db: Session, user_id: int):
    personal_tools = get_task_tools(db, user_id)
    group_tools = get_group_tools(db, user_id)
    tools = personal_tools + group_tools
    llm_with_tools = llm.bind_tools(tools)

    def agent_node(state: State):
        messages = [
            SystemMessage(content=SYSTEM_PROMPT),
            *state["messages"]
        ]
        response = llm_with_tools.invoke(messages)
        return {"messages": [response]}

    graph_builder = StateGraph(State)
    graph_builder.add_node("agent", agent_node)
    graph_builder.add_edge(START, "agent")

    tool_node = ToolNode(tools)
    graph_builder.add_node("tools", tool_node)

    graph_builder.add_conditional_edges(
        "agent",
        tools_condition
    )

    graph_builder.add_edge("tools", "agent")

    graph = graph_builder.compile(checkpointer=checkpointer)

    return graph

    




