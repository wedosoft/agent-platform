from fastapi import APIRouter

from app.api.routes import (
    admin,
    agents,
    assist,
    chat,
    common_documents,
    file_search,
    health,
    multitenant,
    onboarding,
    pipeline,
    sessions,
    sync,
)
from app.core.config import get_settings


def get_api_router() -> APIRouter:
    settings = get_settings()
    router = APIRouter(prefix=settings.api_prefix)
    router.include_router(health.router)
    router.include_router(sessions.router)
    router.include_router(agents.router)
    router.include_router(chat.router)
    router.include_router(common_documents.router)
    router.include_router(pipeline.router)
    router.include_router(file_search.router)
    router.include_router(multitenant.router)  # Multitenant routes at /api/*
    router.include_router(assist.router)  # FDK Custom App assist API
    router.include_router(admin.router)  # Admin API for tenant management
    router.include_router(sync.router, prefix="/sync")  # Sync API for data synchronization
    router.include_router(onboarding.router)  # Onboarding API
    return router
