from datetime import datetime, timezone
from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
def read_health() -> dict:
    return {
        "status": "ok",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
