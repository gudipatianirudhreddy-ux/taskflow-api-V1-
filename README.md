# TaskAPI 🚀

A collaborative task management backend built with **FastAPI**. TaskAPI provides secure Google authentication, personal and group task management, invitations and memberships, and an AI assistant that can understand requests and perform task and group operations through authenticated tools.

## 🚀 Live Demo

**API Documentation:** https://taskflow-api-v1-225t.onrender.com/docs

Try the API directly through the interactive Swagger UI.

## 💡 Why TaskAPI

Hackathon teams of 3–4 often divide work quickly, but during a 24–48 hour sprint it is easy to lose track of ownership, deadlines, priorities, and context. TaskAPI keeps team work organized in one place while an AI assistant can work with the same personal and group data.

The project also practices production-oriented backend patterns such as relational modeling, OAuth + JWT authentication, role-based access control, database migrations, and tool-driven AI workflows.

## ✨ Features

### Authentication & Security
- Google OAuth 2.0 login
- JWT-based authentication
- Protected API endpoints
- Authenticated AI operations scoped to the current user
- Group membership and owner-based authorization

### Personal Task Management
- Create, view, update, and delete personal tasks
- Update title, content, priority, due date, and completion state
- Priorities: LOW, MEDIUM, HIGH, URGENT
- Optional due dates

### Group Management
- Create groups
- View groups the current user belongs to
- View group information and members
- Update group details
- Delete groups as the owner
- Owner is automatically added as a group member

### Member & Invitation Management
- Invite users by email
- Accept invitations using secure tokens
- View group members and roles
- Remove members
- Leave a group

### Group Task Management
- Create tasks for group members
- View all tasks in a group
- View group tasks assigned to the current user
- Assign tasks to group members
- Update group task details, assignee, priority, due date, and completion state
- Delete group tasks
- Owner-only controls for creating, updating, and deleting group tasks

## 🤖 AI Assistant — TaskAPI V2

TaskAPI V2 evolves the AI assistant from a simple conversational interface into a **tool-using task agent**. Users can describe what they want in natural language, and the agent can retrieve relevant data, choose appropriate tools, and carry out supported task operations within the authenticated user's permissions.

### Agent Capabilities
- Understand natural-language requests about personal tasks and group work
- Create, retrieve, update, complete, and delete personal tasks through conversation
- Discover the user's groups and inspect group information and members
- Create, retrieve, update, and delete group tasks where the user has permission
- Retrieve group tasks assigned to the current user
- Resolve group names using available group context
- Preserve conversation context across turns using persistent conversation threads
- Handle relative dates such as “today”, “tomorrow”, or “next Monday” through a date/time tool
- Recommend what to focus on based on retrieved task priority, due dates, completion state, overdue status, and task context
- Keep database operations scoped to the authenticated user and enforce group permissions in backend tools

### 🧠 Task Intelligence

The agent can do more than repeat a task list. For requests such as “What should I work on first?” or “What should I focus on today?”, it retrieves relevant tasks and reasons over their:

- Priority
- Due date and overdue status
- Completion status
- Task context and content
- Personal versus group-task context

These recommendations are advisory: the agent uses the task data available to it and explains what the user could focus on.

### 🧑‍⚖️ Human-in-the-Loop (HITL)

TaskAPI V2 introduces a human approval step for **personal-task deletion** so a destructive action is not carried out immediately after the agent proposes it.

1. The user asks the agent to delete a personal task.
2. The LangGraph workflow pauses and returns an approval request containing the task details.
3. The user explicitly accepts or rejects the request.
4. On acceptance, the workflow resumes and the backend rechecks that the task belongs to the authenticated user and still exists before deleting it.
5. On rejection, the deletion is cancelled and the task remains unchanged.

The approval decision is sent to `POST /ai/chat` using the same conversation `thread_id` that was paused. The decision values are `accept` and `reject`.

**Current scope:** HITL approval is implemented for personal-task deletion. It should not be assumed to apply to group-task deletion or other actions.

### 🏗️ AI Architecture

The assistant is built with **LangChain + LangGraph** and uses **Groq** through `ChatGroq` with the `openai/gpt-oss-120b` model.

The workflow combines:
- Tool calling for database-backed task and group actions
- LangGraph state management and conditional tool execution
- Interrupt/resume control flow for human approval before personal-task deletion
- PostgreSQL-backed checkpointing for conversation state
- Persistent AI conversation records linked to authenticated users
- A shared tool layer covering personal and group workflows

The assistant follows an intent-driven flow:

`UNDERSTAND → RETRIEVE → REASON → ACT / REQUEST APPROVAL → RESPOND`

### AI Conversation Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/ai/conversation` | Create a new AI conversation thread |
| GET | `/ai/conversation` | List the current user's AI conversations |
| POST | `/ai/chat` | Send a message or submit an approval decision on a conversation thread |

## 🛠️ Tech Stack

### Backend
- FastAPI
- Python
- PostgreSQL
- SQLAlchemy ORM
- Alembic
- Pydantic

### Authentication & Communication
- Google OAuth 2.0
- JWT
- SMTP email service

### AI
- LangChain
- LangGraph
- LangChain Groq
- Groq API
- `openai/gpt-oss-120b`
- PostgreSQL-backed LangGraph checkpointing

## 📂 Project Structure

```text
app/
├── routes/
│   ├── ai.py
│   ├── groups.py
│   └── tasks.py
├── services/
│   ├── ai_service.py
│   ├── group_ai_service.py
│   ├── checkpoint.py
│   └── email_service.py
├── models.py
├── schemas.py
├── database.py
├── oauth.py
├── auth.py
├── utils.py
├── config.py
└── main.py
```

## 📌 API Endpoints

### Authentication

| Method | Endpoint |
|--------|----------|
| GET | `/auth/google/login` |
| GET | `/auth/google/callback` |

### Groups

| Method | Endpoint |
|--------|----------|
| GET | `/groups` |
| POST | `/groups` |
| GET | `/groups/{group_id}` |
| PATCH | `/groups/{group_id}` |
| DELETE | `/groups/{group_id}` |

### Invitations

| Method | Endpoint |
|--------|----------|
| POST | `/groups/{group_id}/invite` |
| GET | `/groups/invitations/{token}/accept` |

### Members

| Method | Endpoint |
|--------|----------|
| GET | `/groups/{group_id}/members` |
| POST | `/groups/{group_id}/leave` |
| DELETE | `/groups/{group_id}/members/{user_id}` |

### Group Tasks

| Method | Endpoint |
|--------|----------|
| POST | `/groups/{group_id}/tasks` |
| GET | `/groups/{group_id}/tasks` |
| GET | `/groups/{group_id}/tasks/{task_id}` |
| GET | `/groups/{group_id}/my-tasks` |
| PATCH | `/groups/{group_id}/tasks/{task_id}` |
| DELETE | `/groups/{group_id}/tasks/{task_id}` |

### Personal Tasks

| Method | Endpoint |
|--------|----------|
| POST | `/tasks` |
| GET | `/tasks` |
| GET | `/tasks/{task_id}` |
| PATCH | `/tasks/{task_id}` |
| DELETE | `/tasks/{task_id}` |

### AI

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/ai/conversation` | Create conversation |
| GET | `/ai/conversation` | List conversations |
| POST | `/ai/chat` | Chat with the AI assistant or submit an approval decision |

## ⚙️ Installation

Clone the repository:

```bash
git clone <repository-url>
cd taskflow-api-V1-
```

Create a virtual environment:

```bash
python -m venv .venv
```

Activate the environment.

**Windows**

```bash
.venv\Scripts\activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Run the server:

```bash
uvicorn app.main:app --reload
```

Swagger Documentation:

```text
http://127.0.0.1:8000/docs
```

## 🔑 Environment Variables

Create a `.env` file:

```env
DATABASE_URL=
SECRET_KEY=
ALGORITHM=
ACCESS_TOKEN_EXPIRE_MINUTES=

GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
SESSION_SECRET_KEY=

SMTP_EMAIL=
SMTP_APP_PASSWORD=

GROQ_API_KEY=
```

The AI features require a valid Groq API key.

## 🗄️ Database & Migrations

TaskAPI uses PostgreSQL with SQLAlchemy and Alembic migrations.

AI conversation metadata is stored in the `ai_conversations` table, while LangGraph uses PostgreSQL-backed checkpointing to preserve conversation state across turns and interrupt/resume operations.

Run migrations with:

```bash
alembic upgrade head
```

## 🧠 How the AI Agent Works

1. An authenticated user creates or selects an AI conversation thread.
2. The user sends a message to `/ai/chat` with the thread ID.
3. The LangGraph workflow provides the model with authenticated personal-task and group-management tools.
4. The model selects tools based on the request and the available conversation context.
5. Tools read or modify application data while enforcing user ownership and group permissions.
6. For task-planning questions, the agent retrieves task data and reasons over priority, deadlines, completion, and overdue status.
7. Before deleting a personal task, the workflow pauses and asks the user to accept or reject the action.
8. If accepted, the backend rechecks ownership and existence before deletion; if rejected, the task is left unchanged.
9. The workflow returns a natural-language response and preserves conversation context for follow-up requests.

## 🔒 Authorization Principles

- AI requests run in the authenticated user's context.
- Users can only access group information when they are members of the group.
- Group-task creation, update, and deletion follow group ownership rules implemented by the backend tools.
- Personal tasks are scoped to the authenticated user.
- Personal-task deletion through the AI agent requires explicit approval.
- The task is rechecked for ownership and existence before deletion after approval.
- The AI is instructed not to invent task, group, member, or database information.

## 👨‍💻 Author

Anirudh
