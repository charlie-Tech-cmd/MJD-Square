from fastapi import APIRouter

from app.api.auth import router as auth_router
from app.api.customers import router as customers_router
from app.api.inventory import router as inventory_router
from app.api.roles import router as roles_router
from app.api.settings import router as settings_router
from app.api.suppliers import router as suppliers_router
from app.api.transactions import router as transactions_router
from app.api.users import router as users_router
from app.api.workflows import router as workflows_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth_router)
api_router.include_router(settings_router)
api_router.include_router(users_router)
api_router.include_router(roles_router)
api_router.include_router(customers_router)
api_router.include_router(suppliers_router)
api_router.include_router(inventory_router)
api_router.include_router(transactions_router)
api_router.include_router(workflows_router)
