from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import get_api_router
from app.core.config import get_settings


settings = get_settings()
app = FastAPI(title=settings.app_name)

allowed_origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "https://localhost:3000",
    "https://ameer-timberless-paragogically.ngrok-free.dev",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(get_api_router())


@app.get("/")
def root() -> dict:
    return {"message": "Agent Platform backend", "api_prefix": settings.api_prefix}
