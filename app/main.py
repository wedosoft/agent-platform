import os
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.router import get_api_router
from app.core.config import get_settings
from app.services.scheduler_service import get_scheduler_service


logger = logging.getLogger(__name__)
settings = get_settings()

# Configure logging
logging.basicConfig(
    level=settings.log_level,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logging.getLogger("app").setLevel(settings.log_level)

# Silence noisy libraries
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """애플리케이션 시작/종료 시 스케줄러 관리"""
    # Startup
    scheduler = get_scheduler_service()
    scheduler.start()
    logger.info("Scheduler started")
    
    yield
    
    # Shutdown
    scheduler.shutdown()
    logger.info("Scheduler stopped")


app = FastAPI(title=settings.app_name, lifespan=lifespan)

allowed_origins = [
    "http://localhost:3000",
    "http://localhost:3001",  # Onboarding frontend
    "http://127.0.0.1:3000",
    "http://127.0.0.1:3001",
    "https://localhost:3000",
    "https://ameer-timberless-paragogically.ngrok-free.dev",
    "https://www.wedosoft.net",
    "https://onboarding.wedosoft.net",
    "https://onboarding-three-pi.vercel.app",
    "https://onboarding-alans-projects-c08c24fe.vercel.app",
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
