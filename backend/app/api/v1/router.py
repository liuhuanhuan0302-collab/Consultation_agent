from fastapi import APIRouter

from app.api.v1.endpoints import admin, health, organization, public


api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(public.router)
api_router.include_router(organization.router)
api_router.include_router(admin.router)
