from datetime import timedelta, datetime
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session
from starlette import status
from .database import SessionLocal
from .models import Users
from passlib.context import CryptContext
from fastapi.security import OAuth2PasswordRequestForm, OAuth2PasswordBearer
from jose import jwt, JWTError
from . import schemas, database, models
from app.Oauth import oauth
import os
import asyncio
SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = os.getenv("ALGORITHM")
router=APIRouter(
    prefix='/auth',
    tags=['auth']
)

# oauth2_bearer = OAuth2PasswordBearer(tokenUrl='auth/google')
oauth2_bearer = OAuth2PasswordBearer(tokenUrl="/auth/google/login")


def access_token(username: str, id: int, expires_delta: timedelta):
    encode={"sub": username, "id":id, "type": "access"}
    expires=datetime.utcnow()+expires_delta
    encode.update({"exp": expires})
    return jwt.encode(encode, SECRET_KEY,ALGORITHM)

def create_refresh_token(username: str, id: int, expires_delta: timedelta):
    encode = {"sub": username, "id": id,"type":"refresh"}
    expires = datetime.utcnow() + expires_delta
    encode.update({"exp": expires})
    return jwt.encode(encode, SECRET_KEY, ALGORITHM)
    

def get_current_user(request: Request):
    token = request.cookies.get("access_token")
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing token")
    if token.startswith("Bearer "):
        token = token.split(" ", 1)[1]  
    try:
        payload=jwt.decode(token, SECRET_KEY,algorithms=[ALGORITHM])
        username: str=payload.get('sub')
        user_id: int =payload.get('id')
        token_type=payload.get('type')
        if token_type!="access":
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid access token")
        if username is None or user_id is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Could not validate user")
        return {'username': username, 'id':user_id}
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Could not validate user")
        
 
@router.get("/google/login")
async def  google_login(request: Request):
    redirect_uri=request.url_for("google_callback")
    print("Redirect URI:", redirect_uri)
    return await oauth.google.authorize_redirect(
        request,
        redirect_uri
    )

@router.get("/google/callback")
async def google_callback(requests: Request,response: Response,db: Session = Depends(database.get_db)):
    token=await oauth.google.authorize_access_token(requests)
    print(token)
    user_info = token["userinfo"]
    user=db.query(models.Users).filter(models.Users.google_id==user_info["sub"]).first()
    if not user:
        user=models.Users(
            google_id=user_info["sub"],
            username=user_info["name"],
            email=user_info["email"]
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    acc_token=access_token(
        username=user.username,
        id=user.id,
        expires_delta=timedelta(minutes=20)
    )
    refresh = create_refresh_token(username=user.username,id=user.id,expires_delta=timedelta(days=7))
    response.set_cookie(
    key="access_token",
    value=acc_token,
    httponly=True,
    secure=True,
    samesite="lax",
    max_age=20 * 60
             )
    response.set_cookie(
    key="refresh_token",
    value=refresh,
    httponly=True,
    secure=True,
    samesite="lax",
    max_age=7 * 24 * 60 * 60
         )
    return {"Message":"Login Successful"}

    
       
    
    
@router.get("/me", response_model=schemas.UserPost)
def get_login(current_user=Depends(get_current_user),db: Session = Depends(database.get_db)):
    users=db.query(models.Users).filter(models.Users.id==current_user["id"]).first()
    if not users:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f"Not authorized")
    return users
    


@router.post("/refresh")
def refresh_token(request: Request, response: Response):
    refresh = request.cookies.get("refresh_token")
    if not refresh:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing refresh token")
    
    try:
        payload=jwt.decode(refresh,SECRET_KEY,algorithms=[ALGORITHM])
        username = payload.get("sub")
        user_id = payload.get("id")
        token_type = payload.get("type")
        if token_type!="refresh":
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")
        if username is None or user_id is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Could not validate user")
        new=access_token(username=username,id=user_id,expires_delta=timedelta(minutes=20))
        response.set_cookie(
            key="access_token",
            value=new,
            httponly=True,
            secure=True,
            samesite="lax",
            max_age=20 * 60
        )
        return {"message": "Access token refreshed successfully"}
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Could not validate user")
    
    
    
@router.post("/Logout")
def logout(response: Response):
    response.delete_cookie("access_token")
    response.delete_cookie("refresh_token")
    return {"message": "Logged out successfully"}

    
            

