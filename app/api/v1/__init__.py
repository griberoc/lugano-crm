from fastapi import APIRouter

from app.api.v1.endpoints.admin import router as admin_router
from app.api.v1.endpoints.catalog import router as catalog_router
from app.api.v1.endpoints.loyalty import router as loyalty_router
from app.api.v1.endpoints.orders import router as orders_router
from app.api.v1.endpoints.profile import router as profile_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(admin_router)
api_router.include_router(catalog_router)
api_router.include_router(orders_router)
api_router.include_router(loyalty_router)
api_router.include_router(profile_router)
