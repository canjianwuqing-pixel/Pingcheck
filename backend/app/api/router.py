from fastapi import APIRouter

from app.api.auth import router as auth_router
from app.api.health import router as health_router
from app.modules.targets.router import router as targets_router
from app.modules.telegram.router import router as telegram_router


api_router = APIRouter(prefix="/api")
api_router.include_router(health_router)
api_router.include_router(auth_router)
api_router.include_router(targets_router)
api_router.include_router(telegram_router)
