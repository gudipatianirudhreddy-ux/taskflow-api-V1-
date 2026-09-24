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

## 🤖 AI Assistant

TaskAPI includes an AI-powered assistant for both personal and collaborative task management.

### AI Capabilities
- Natural-language task and group management
- Create, read, update, and delete personal tasks through conversation
- Discover the groups a user belongs to
- Inspect group information and members
- Create, read, update, and delete group tasks where the user has permission
- Retrieve group tasks assigned to the authenticated user
- Understand requests such as “show my tasks”, including relevant personal and group work
- Resolve group names using available group context
- Preserve conversation context across turns
- Handle relative dates such as “today”, “tomorrow”, or “next Monday” through a date/time tool
- Enforce authorization through the backend tools
- Avoid exposing internal IDs unnecessarily

### 🧠 Task Intelligence

The assistant can now go beyond simply retrieving task lists and provide **reasoned task recommendations**.

When a user asks questions such as:

- “What should I work on first?”
- “What should I focus on today?”
- “Which task is most urgent?”

The assistant retrieves the relevant current tasks and considers:

- Priority
- Due date
- Completion status
- Overdue status
- Task context and content
- Whether the task is personal or group-related

It then provides a recommendation rather than simply repeating the task list. Facts retrieved from TaskFlow are kept distinct from the assistant's own reasoning.

### AI Architecture

The assistant is built with **LangChain + LangGraph** and uses **Groq** through `ChatGroq` with the `openai/gpt-oss-120b` model.

The AI workflow combines:

- Tool calling for database-backed task and group actions
- LangGraph state management and conditional tool execution
- PostgreSQL-backed checkpointing for conversation state
- Persistent AI conversation records linked to authenticated users
- A shared tool layer covering both personal and group workflows

The assistant follows an intent-driven flow:

`UNDERSTAND → RETRIEVE → REASON → RESPOND`

### AI Conversation Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/ai/conversation` | Create a new AI conversation thread |
| GET | `/ai/conversation` | List the current user's AI conversations |
| POST | `/ai/chat` | Send a message to the AI assistant using a conversation thread |

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
| POST | `/ai/chat` | Chat with the AI assistant |

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

AI conversation metadata is stored in the `ai_conversations` table, while LangGraph uses PostgreSQL-backed checkpointing to preserve conversation state.

Run migrations with:

```bash
alembic upgrade head
```

## 🧠 How the AI Assistant Works

1. An authenticated user creates or selects an AI conversation thread.
2. The message is sent to `/ai/chat` with the thread ID.
3. The LangGraph workflow gives the model authenticated personal-task and group-management tools.
4. The model selects the required tools based on the user's request.
5. Tools read or modify application data while enforcing membership and owner permissions.
6. For advice and prioritization requests, the assistant analyzes retrieved task data and produces a reasoned recommendation.
7. The workflow returns a natural-language response and preserves conversation context for follow-up requests.

## 🔒 Authorization Principles

- AI requests run in the authenticated user's context.
- Users can only access group information when they are members of the group.
- Group-task creation, update, and deletion follow group ownership rules implemented by the backend tools.
- Personal tasks are scoped to the authenticated user.
- The AI is instructed not to invent task, group, member, or database information.

## 👨‍💻 Author

Anirudh
