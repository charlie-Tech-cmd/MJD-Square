from fastapi import APIRouter

from app.api.auth import router as auth_router
from app.api.roles import router as roles_router
from app.api.settings import router as settings_router
from app.api.users import router as users_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth_router)
api_router.include_router(settings_router)
api_router.include_router(users_router)
api_router.include_router(roles_router)
