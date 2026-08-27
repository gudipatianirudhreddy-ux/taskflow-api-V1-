from fastapi import APIRouter, Depends, HTTPException,status
from .. import database,models,schemas
from sqlalchemy.orm import Session
from typing import List
from ..auth import get_current_user
import secrets
from datetime import timedelta, datetime,timezone
from app.services.email_service import send_group_invitation
from app.models import InvitationStatus,Role

router=APIRouter(
    prefix='/ai',
    tags=['Ai_Features']
)
