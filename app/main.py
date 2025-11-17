from fastapi import FastAPI

from app.api.router import get_api_router
from app.core.config import get_settings


settings = get_settings()
app = FastAPI(title=settings.app_name)
app.include_router(get_api_router())


@app.get("/")
def root() -> dict:
    return {"message": "Agent Platform backend", "api_prefix": settings.api_prefix}
