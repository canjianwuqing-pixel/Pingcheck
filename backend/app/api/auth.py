from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, Field

from app.core.security import verify_password
from app.database import create_session, delete_session
from app.dependencies import (
    SESSION_COOKIE_NAME,
    get_settings,
    require_admin,
)


router = APIRouter(prefix="/auth", tags=["认证"])


class LoginRequest(BaseModel):
    password: str = Field(min_length=1, max_length=256)


class AuthState(BaseModel):
    authenticated: bool


@router.post("/login", response_model=AuthState)
def login(payload: LoginRequest, request: Request, response: Response) -> AuthState:
    settings = get_settings(request)
    if not verify_password(payload.password, settings.admin_password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="管理密码错误",
        )

    token, _ = create_session(
        settings.database_path,
        settings.session_secret,
        settings.session_max_age_seconds,
    )
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        max_age=settings.session_max_age_seconds,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/",
    )
    return AuthState(authenticated=True)


@router.get("/me", response_model=AuthState)
def current_admin(_: Annotated[None, Depends(require_admin)]) -> AuthState:
    return AuthState(authenticated=True)


@router.post("/logout", response_model=AuthState)
def logout(request: Request, response: Response) -> AuthState:
    settings = get_settings(request)
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if token:
        delete_session(settings.database_path, settings.session_secret, token)
    response.delete_cookie(
        key=SESSION_COOKIE_NAME,
        path="/",
        secure=settings.cookie_secure,
        httponly=True,
        samesite="lax",
    )
    return AuthState(authenticated=False)
