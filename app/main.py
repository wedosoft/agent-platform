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
logging.getLogger("hpack").setLevel(logging.WARNING)


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

# CORS 설정 수정: FDK 로컬 개발 환경 및 ngrok 지원
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:10001",  # FDK Local
        "http://localhost:8000",   # Backend Local
        "http://localhost:3000",
        "http://localhost:3001",
        "http://localhost:5173",   # Vite 프론트엔드(온보딩)
    ],
    allow_origin_regex="https?://.*",  # 모든 Origin 허용 (개발 편의성)
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
