from fastapi import APIRouter

from app.api.v1.endpoints import admin, health, public


api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(public.router)
api_router.include_router(admin.router)
