# TaskAPI 🚀

A collaborative task management backend built with **FastAPI** that allows users to authenticate with Google, create groups, invite members, assign tasks, and collaborate securely.

## 🚀 Live Demo

**API Documentation:** https://taskflow-api-v1-225t.onrender.com/docs

> Try the API directly through the interactive Swagger UI.


## 💡 Why TaskAPI
Hackathon teams of 3-4 usually split up tasks early on, but over a 24-48 hour sprint it's easy to lose track of who's doing what, forget context on a task you picked up hours ago, or step on a teammate's work. TaskAPI is a lightweight team task tracker built for exactly this: create a group for your team, assign tasks per person, and keep everyone's progress visible in one place — so the team spends less time re-explaining status and more time building. Built to practice production-grade backend patterns: relational modeling, secure OAuth + JWT auth, and role-based access control
## ✨ Features

### Authentication
- Google OAuth 2.0 Login
- JWT Authentication
- Protected API endpoints

### Group Management
- Create groups
- View groups
- Update group details
- Delete groups
- Owner automatically added as a group member

### Member Management
- Invite users via email
- Accept invitation using secure token
- View group members
- Remove members
- Leave a group

### Task Management
- Create group tasks
- Assign tasks to group members
- View all tasks in a group
- View individual task
- View tasks assigned to the logged-in user
- Update task
- Delete task

---

## 🛠️ Tech Stack

- FastAPI
- Python
- PostgreSQL
- SQLAlchemy ORM
- Alembic
- Google OAuth
- JWT
- Pydantic
- SMTP Email Service

---

## 📂 Project Structure

```text
app/
├── routes/
├── models.py
├── schemas.py
├── database.py
├── oauth.py
├── auth.py
├── utils.py
├── config.py
└── main.py
```

---

## 📌 API Endpoints

### Authentication

| Method | Endpoint |
|---------|----------|
| GET | `/auth/google/login` |
| GET | `/auth/google/callback` |

### Groups

| Method | Endpoint |
|---------|----------|
| GET | `/groups` |
| POST | `/groups` |
| GET | `/groups/{group_id}` |
| PATCH | `/groups/{group_id}` |
| DELETE | `/groups/{group_id}` |

### Invitations

| Method | Endpoint |
|---------|----------|
| POST | `/groups/{group_id}/invite` |
| GET | `/groups/invitations/{token}/accept` |

### Members

| Method | Endpoint |
|---------|----------|
| GET | `/groups/{group_id}/members` |
| POST | `/groups/{group_id}/leave` |
| DELETE | `/groups/{group_id}/members/{user_id}` |

### Tasks

| Method | Endpoint |
|---------|----------|
| POST | `/groups/{group_id}/tasks` |
| GET | `/groups/{group_id}/tasks` |
| GET | `/groups/{group_id}/tasks/{task_id}` |
| GET | `/groups/{group_id}/my-tasks` |
| PATCH | `/groups/{group_id}/tasks/{task_id}` |
| DELETE | `/groups/{group_id}/tasks/{task_id}` |

---

## ⚙️ Installation

Clone the repository

```bash
git clone <repository-url>
cd taskapi
```

Create a virtual environment

```bash
python -m venv .venv
```

Activate the environment

Windows

```bash
.venv\Scripts\activate
```

Install dependencies

```bash
pip install -r requirements.txt
```

Run the server

```bash
uvicorn app.main:app --reload
```

Swagger Documentation

```
http://127.0.0.1:8000/docs
```

---

## 🔑 Environment Variables

Create a `.env` file.

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
```

---

## 📖 Future Improvements

- AI-powered task suggestions
- RAG-based document assistant
- Team chat
- Notifications
- Deadline reminders
- Analytics dashboard

---

## 👨‍💻 Author

Anirudh
