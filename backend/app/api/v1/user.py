from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.api.deps import get_current_user
from app.models.user import User

router = APIRouter()


class UserUpdate(BaseModel):
    timezone: str | None = Field(default=None, pattern=r"^[A-Za-z_/+]+$")
    briefing_time: str | None = Field(default=None, pattern=r"^([01]?[0-9]|2[0-3]):[0-5][0-9]$")
    briefing_enabled: bool | None = None


class UserProfile(BaseModel):
    id: str
    email: str
    name: str | None
    picture: str | None
    timezone: str
    briefing_time: str
    briefing_enabled: bool

    class Config:
        from_attributes = True


@router.get("/me", response_model=UserProfile)
async def get_profile(user: User = Depends(get_current_user)):
    return user


@router.patch("/me", response_model=UserProfile)
async def update_profile(
    update: UserUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if update.timezone is not None:
        user.timezone = update.timezone
    if update.briefing_time is not None:
        user.briefing_time = update.briefing_time
    if update.briefing_enabled is not None:
        user.briefing_enabled = update.briefing_enabled

    await db.commit()
    await db.refresh(user)
    return user