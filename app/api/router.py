from fastapi import APIRouter

from app.api.routes import agents, chat, common_documents, health, pipeline, sessions
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
    return router
