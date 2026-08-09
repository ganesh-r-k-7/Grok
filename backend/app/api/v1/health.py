from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.database import get_db
from app.utils.errors import AppError

router = APIRouter()


@router.get("/health")
async def health_check() -> dict:
    return {"status": "healthy", "service": "grok-backend"}


@router.get("/ready")
async def readiness_check(db: AsyncSession = Depends(get_db)) -> dict:
    try:
        await db.execute(text("SELECT 1"))
    except Exception:
        raise AppError("Database unavailable", status_code=503, error_type="service_unavailable")

    # Redis check is done in main.py
    return {"status": "ready", "service": "grok-backend"}