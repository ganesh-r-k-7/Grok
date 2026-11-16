from fastapi import APIRouter

from app.api.v1 import ai, auth, calendar, health, tasks, user

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(user.router, prefix="/user", tags=["user"])
api_router.include_router(health.router, prefix="", tags=["health"])
api_router.include_router(tasks.router, prefix="/tasks", tags=["tasks"])
api_router.include_router(ai.router, prefix="/ai", tags=["ai"])
api_router.include_router(calendar.router, prefix="/calendar", tags=["calendar"])
