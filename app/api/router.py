from fastapi import APIRouter

from app.api.routes import (
    admin,
    agents,
    assist,
    chat,
    channel_fdk_v1,
    channel_web_v1,
    common_documents,
    curriculum,
    file_search,
    health,
    multitenant,
    onboarding,
    pipeline,
    sessions,
    sync,
    tickets,
)
from app.core.config import get_settings


def get_api_router() -> APIRouter:
    settings = get_settings()
    router = APIRouter(prefix=settings.api_prefix)
    router.include_router(health.router)
    router.include_router(sessions.router)
    router.include_router(agents.router)
    # Legacy chat endpoints (keep)
    router.include_router(chat.router)
    # Channel BFF (new, non-breaking)
    router.include_router(channel_fdk_v1.router)
    router.include_router(common_documents.router)
    router.include_router(pipeline.router)
    router.include_router(file_search.router)
    # Multitenant chat endpoints (namespaced; fixes /api/chat route collision)
    router.include_router(multitenant.router, prefix="/multitenant")
    # Channel BFF (new, non-breaking)
    router.include_router(channel_web_v1.router)
    router.include_router(assist.router)  # FDK Custom App assist API
    router.include_router(admin.router)  # Admin API for tenant management
    router.include_router(sync.router, prefix="/sync")  # Sync API for data synchronization
    router.include_router(onboarding.router)  # Onboarding API
    router.include_router(curriculum.router)  # Curriculum API for product training
    router.include_router(tickets.router)  # Ticket Analysis API (schema-validated)
    return router
