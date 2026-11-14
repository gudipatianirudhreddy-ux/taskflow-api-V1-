from fastapi import FastAPI, HTTPException, status, Depends
from . import schemas
from . import database, models
from sqlalchemy.orm import Session
from typing import List
from . import auth
from .routes import tasks, groups, ai
from starlette.middleware.sessions import SessionMiddleware
from dotenv import load_dotenv
from fastapi.middleware.cors import CORSMiddleware
import os

load_dotenv()

app = FastAPI()

frontend_url = os.getenv("FRONTEND_URL", "http://localhost:3000")
allowed_origins = [
    origin.strip()
    for origin in os.getenv("ALLOWED_ORIGINS", f"{frontend_url},http://localhost:3000").split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(
    SessionMiddleware,
    secret_key=os.getenv("SESSION_SECRET_KEY", "session-secret-key-default")
)

app.include_router(auth.router)
app.include_router(tasks.router)
app.include_router(groups.router)
app.include_router(ai.router)

@app.get("/")
def root():
    return {"message": "Welcome to taskapi"}
