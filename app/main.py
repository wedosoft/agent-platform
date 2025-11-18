import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.router import get_api_router
from app.core.config import get_settings


settings = get_settings()
app = FastAPI(title=settings.app_name)

allowed_origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "https://localhost:3000",
    "https://ameer-timberless-paragogically.ngrok-free.dev",
    "https://www.wedosoft.net",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(get_api_router())

# Mount static files for the frontend
static_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")
if os.path.exists(static_dir):
    app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")
else:
    @app.get("/")
    def root() -> dict:
        return {"message": "Agent Platform backend", "api_prefix": settings.api_prefix}
