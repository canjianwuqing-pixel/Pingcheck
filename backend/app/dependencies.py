from fastapi import HTTPException, Request, status

from app.core.config import Settings
from app.database import session_is_valid


SESSION_COOKIE_NAME = "pingcheck_session"


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def require_admin(request: Request) -> None:
    settings = get_settings(request)
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if not token or not session_is_valid(
        settings.database_path, settings.session_secret, token
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="登录已失效，请重新登录",
        )
