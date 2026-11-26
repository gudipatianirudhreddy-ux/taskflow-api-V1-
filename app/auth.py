from datetime import timedelta, datetime,timezone
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
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
import secrets
import hashlib
from sqlalchemy import delete
from .schemas import NativeExchangeRequest
SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = os.getenv("ALGORITHM")

router = APIRouter(
    prefix='/auth',
    tags=['auth']
)

oauth2_bearer = OAuth2PasswordBearer(tokenUrl="/auth/google/login")


def get_cookie_settings(request: Request):
    env_secure = os.getenv("COOKIE_SECURE")
    if env_secure is not None:
        secure = env_secure.lower() == "true"
    else:
        secure = request.url.scheme == "https"

    env_samesite = os.getenv("COOKIE_SAMESITE")
    if env_samesite is not None:
        samesite = env_samesite.lower()
    else:
        samesite = "none" if secure else "lax"

    return secure, samesite


def access_token(username: str, id: int, expires_delta: timedelta):
    encode = {"sub": username, "id": id, "type": "access"}
    expires = datetime.utcnow() + expires_delta
    encode.update({"exp": expires})
    return jwt.encode(encode, SECRET_KEY, ALGORITHM)


def create_refresh_token(username: str, id: int, expires_delta: timedelta):
    encode = {"sub": username, "id": id, "type": "refresh"}
    expires = datetime.utcnow() + expires_delta
    encode.update({"exp": expires})
    return jwt.encode(encode, SECRET_KEY, ALGORITHM)


def get_current_user(request: Request):
    token = request.cookies.get("access_token")
    if not token:
        auth_hdr = request.headers.get("Authorization")
        if auth_hdr and auth_hdr.startswith("Bearer "):
            token = auth_hdr.split(" ", 1)[1]
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing token")
    if token.startswith("Bearer "):
        token = token.split(" ", 1)[1]
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get('sub')
        user_id: int = payload.get('id')
        token_type = payload.get('type')
        if token_type != "access":
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid access token")
        if username is None or user_id is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Could not validate user")
        return {'username': username, 'id': user_id}
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Could not validate user")


def is_safe_redirect_url(url: str) -> bool:
    if not url:
        return False
    frontend_base = os.getenv("FRONTEND_URL", "http://localhost:3000")
    if (url.startswith("http://localhost:") or
        url.startswith("http://localhost/") or
        url == "http://localhost" or
        url.startswith("http://127.0.0.1:") or
        url.startswith("http://127.0.0.1/") or
        url == "http://127.0.0.1" or
        url.startswith("https://localhost:") or
        url.startswith("https://127.0.0.1:") or
        url.startswith("obsidiantodo://") or
        url.startswith(frontend_base)):
        return True
    return False


@router.get("/google/login")
async def google_login(request: Request, redirect_url: str | None = None):
    if redirect_url and is_safe_redirect_url(redirect_url):
        request.session["post_login_redirect"] = redirect_url

    redirect_uri = request.url_for("google_callback")
    print("Redirect URI:", redirect_uri)
    return await oauth.google.authorize_redirect(
        request,
        redirect_uri
    )


@router.get("/google/callback")
async def google_callback(requests: Request, db: Session = Depends(database.get_db)):
    target_url = requests.session.pop("post_login_redirect", None) or os.getenv("FRONTEND_URL", "http://localhost:3000")
    try:
        token = await oauth.google.authorize_access_token(requests)
    except Exception as e:
        print("OAuth token error:", e)
        sep = "&" if "?" in target_url else "?"
        error_url = f"{target_url}{sep}error=auth_failed"
        return RedirectResponse(url=error_url, status_code=status.HTTP_302_FOUND)

    user_info = token.get("userinfo") if isinstance(token, dict) else None
    if not user_info or "sub" not in user_info:
        sep = "&" if "?" in target_url else "?"
        return RedirectResponse(url=f"{target_url}{sep}error=invalid_userinfo", status_code=status.HTTP_302_FOUND)

    user = db.query(models.Users).filter(models.Users.google_id == user_info["sub"]).first()
    if not user:
        user = models.Users(
            google_id=user_info["sub"],
            username=user_info.get("name", user_info.get("email", "User")),
            email=user_info["email"]
        )
        db.add(user)
        db.commit()
        db.refresh(user)

    exp_minutes = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "20"))
    exp_days = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7"))

    acc_token = access_token(
        username=user.username,
        id=user.id,
        expires_delta=timedelta(minutes=exp_minutes)
    )
    refresh = create_refresh_token(
        username=user.username,
        id=user.id,
        expires_delta=timedelta(days=exp_days)
    )

    secure, samesite = get_cookie_settings(requests)

    response = RedirectResponse(url=target_url, status_code=status.HTTP_302_FOUND)
    response.set_cookie(
        key="access_token",
        value=acc_token,
        httponly=True,
        secure=secure,
        samesite=samesite,
        max_age=exp_minutes * 60
    )
    response.set_cookie(
        key="refresh_token",
        value=refresh,
        httponly=True,
        secure=secure,
        samesite=samesite,
        max_age=exp_days * 24 * 60 * 60
    )
    return response


@router.get("/me", response_model=schemas.UserPost)
def get_login(current_user=Depends(get_current_user), db: Session = Depends(database.get_db)):
    users = db.query(models.Users).filter(models.Users.id == current_user["id"]).first()
    if not users:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authorized")
    return users


@router.post("/refresh")
def refresh_token(request: Request, response: Response):
    refresh = request.cookies.get("refresh_token")
    if not refresh:
        auth_hdr = request.headers.get("Authorization")
        if auth_hdr and auth_hdr.startswith("Bearer "):
            refresh = auth_hdr.split(" ", 1)[1]
    if not refresh:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing refresh token")

    try:
        payload = jwt.decode(refresh, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        user_id = payload.get("id")
        token_type = payload.get("type")
        if token_type != "refresh":
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")
        if username is None or user_id is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Could not validate user")

        exp_minutes = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "20"))
        new = access_token(username=username, id=user_id, expires_delta=timedelta(minutes=exp_minutes))
        secure, samesite = get_cookie_settings(request)
        response.set_cookie(
            key="access_token",
            value=new,
            httponly=True,
            secure=secure,
            samesite=samesite,
            max_age=exp_minutes * 60
        )
        return {"message": "Access token refreshed successfully"}
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Could not validate user")


@router.post("/Logout")
def logout(request: Request, response: Response):
    secure, samesite = get_cookie_settings(request)
    response.delete_cookie("access_token", samesite=samesite, secure=secure)
    response.delete_cookie("refresh_token", samesite=samesite, secure=secure)
    return {"message": "Logged out successfully"}


@router.get("/health")
def health():
    return {"message": "Health check"}


@router.get("/google/native/login", name="google_native_login")
async def google_native_login(request: Request):
    callback_url=request.url_for("google_native_callback")
    return await oauth.google.authorize_redirect(request, callback_url)


@router.get("/google/native/callback",name="google_native_callback")
async def google_native_callback(request: Request, db: Session=Depends(database.get_db)):
    native_redirect_url=os.getenv("NATIVE_REDIRECT_URL")
    if not native_redirect_url:
        raise HTTPException(status_code=500, detail="Native redirect url is not configured")
    try:
        token=await oauth.google.authorize_access_token(request)
        userinfo=token.get("userinfo")
        if not userinfo or not userinfo.get("sub"):
            return RedirectResponse(f"{native_redirect_url}? error=invalid_google_user")
    except Exception:
        return RedirectResponse(f"{native_redirect_url}? error=google_auth_failed")
    google_id=userinfo["sub"]
    user=(db.query(models.Users).filter(models.Users.google_id==google_id).first())
    if not user:
        user=models.Users(google_id=google_id,
                          username=(userinfo.get("name") or
                                    userinfo.get("email") or
                                    "User"),
                                    email=userinfo.get("email"))
        db.add(user)
        db.commit()
        db.refresh(user)
    raw_code=secrets.token_urlsafe(32)
    code_hash=hashlib.sha256(raw_code.encode()).hexdigest()
    login_code=models.NativeLoginCode(
        user_id=user.id,
        code_hash=code_hash,
        expires_at=datetime.now(timezone.utc)+timedelta(seconds=100)
    )
    db.add(login_code)
    db.commit()
    return RedirectResponse(f"{native_redirect_url}? code={raw_code}",status_code=302)


@router.post("/google.native/exhange")
def exhange_native_login_code(payload: NativeExchangeRequest,db: Session=Depends(database.get_db)):
    code_hash=hashlib.sha256(payload.code.encode()).hexdigest()
    statement=(delete(models.NativeLoginCode).where(models.NativeLoginCode.code_hash==code_hash,models.NativeLoginCode.expires_at> datetime.now(timezone.utc)).returning(models.NativeLoginCode.user_id))
    result=db.execute(statement)
    user_id=result.scalar_one_or_none()
    db.commit()
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired login code",
        )
    user=(db.query(models.Users).filter(models.Users.id==user_id).first())
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )
    exp_minutes=int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES","20"))
    exp_days=int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS","7"))
    access=access_token(
        username=user.username,
        id=user.id,
        expires_delta=timedelta(minutes=exp_minutes)
    )
    refresh=create_refresh_token(
        username=user.username,
        id=user.id,
        expires_delta=timedelta(days=exp_days)
    )
    return {
        "access_token":access,
        "refresh_token":refresh,
        "token_type":"bearer"
    }





    