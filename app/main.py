from fastapi import FastAPI,HTTPException,status,Depends
from .import schemas
from . import database,models
from sqlalchemy.orm import Session
from typing import List
from . import auth
from .routes import tasks,groups,ai
from starlette.middleware.sessions import SessionMiddleware
from dotenv import load_dotenv
import os
load_dotenv()
app=FastAPI()
app.include_router(auth.router)
app.include_router(tasks.router)
app.include_router(groups.router)
app.include_router(ai.router)
@app.get("/")
def root():
    return {"message":"Welcome to taskapi"}

app.add_middleware(SessionMiddleware,
    secret_key=os.getenv("SESSION_SECRET_KEY"))
