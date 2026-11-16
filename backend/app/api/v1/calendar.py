"""Read-only Google Calendar endpoints."""

from datetime import datetime

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.database import get_db
from app.models.user import User
from app.services.google_calendar import (
    GoogleCalendarError,
    GoogleCalendarNotConnectedError,
    get_google_calendar_service,
)
from app.utils.errors import ConflictError

router = APIRouter()


class CalendarEventTime(BaseModel):
    date_time: str | None = None
    date: str | None = None
    timezone: str | None = None


class CalendarEvent(BaseModel):
    id: str | None = None
    summary: str | None = None
    location: str | None = None
    start: CalendarEventTime
    end: CalendarEventTime
    html_link: str | None = None


@router.get("/events", response_model=list[CalendarEvent])
async def list_calendar_events(
    time_min: datetime | None = None,
    time_max: datetime | None = None,
    max_results: int = Query(50, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[CalendarEvent]:
    """List primary-calendar events for the connected user."""
    try:
        events = await get_google_calendar_service(db, user).list_events(
            time_min, time_max, max_results
        )
    except GoogleCalendarNotConnectedError as exc:
        raise ConflictError("Google Calendar is not connected") from exc
    except GoogleCalendarError as exc:
        raise ConflictError("Unable to load Google Calendar events") from exc
    return [CalendarEvent.model_validate(event) for event in events]
