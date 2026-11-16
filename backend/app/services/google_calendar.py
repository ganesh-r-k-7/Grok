"""Google Calendar API service for read-only calendar access."""

import asyncio
from datetime import UTC, datetime, timedelta

from cryptography.exceptions import InvalidTag
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.oauth_token import OAuthToken
from app.models.user import User
from app.services.encryption import get_encryption_service
from app.services.google_oauth import TokenExchangeError, get_google_oauth_service


class GoogleCalendarError(Exception):
    """Base exception for Google Calendar errors."""

    def __init__(self, message: str, details: dict | None = None):
        super().__init__(message)
        self.details = details or {}


class GoogleCalendarNotConnectedError(GoogleCalendarError):
    """Raised when user has not connected Google Calendar."""


class GoogleCalendarTokenError(GoogleCalendarError):
    """Raised when token is invalid, expired, or revoked."""


class GoogleCalendarRateLimitError(GoogleCalendarError):
    """Raised when Google API rate limit is exceeded."""


class GoogleCalendarService:
    """Service for interacting with Google Calendar API (read-only)."""

    # Buffer time before expiry to proactively refresh (5 minutes)
    TOKEN_REFRESH_BUFFER_SECONDS = 300

    def __init__(self, db: AsyncSession, user: User):
        self.db = db
        self.user = user
        self._encryption = get_encryption_service()
        self._oauth_service = get_google_oauth_service()
        self._calendar_client = None

    async def _get_oauth_token(self) -> OAuthToken:
        """Get the user's Google OAuth token."""
        result = await self.db.execute(
            select(OAuthToken).where(
                OAuthToken.user_id == self.user.id,
                OAuthToken.provider == "google",
            )
        )
        oauth_token = result.scalar_one_or_none()

        if not oauth_token:
            raise GoogleCalendarNotConnectedError(
                "Google Calendar not connected. Please connect your account first.",
                details={"user_id": str(self.user.id)},
            )

        return oauth_token

    def _is_token_expired_or_expiring(self, expires_at: datetime) -> bool:
        """Check if token is expired or close to expiry."""
        now = datetime.now(UTC)
        buffer = expires_at - now
        return buffer.total_seconds() <= self.TOKEN_REFRESH_BUFFER_SECONDS

    async def _refresh_access_token(self, oauth_token: OAuthToken) -> str:
        """Refresh the access token using the refresh token."""
        if not oauth_token.refresh_token_enc:
            raise GoogleCalendarTokenError(
                "No refresh token available. Please reconnect your Google Calendar account.",
                details={"user_id": str(self.user.id)},
            )

        try:
            refresh_token = self._encryption.decrypt(oauth_token.refresh_token_enc)
        except (ValueError, InvalidTag) as e:
            raise GoogleCalendarTokenError(
                "Failed to decrypt refresh token. Please reconnect your account.",
                details={"user_id": str(self.user.id), "error": str(e)},
            )

        try:
            token_data = await self._oauth_service.refresh_access_token(refresh_token)
        except TokenExchangeError as e:
            raise GoogleCalendarTokenError(
                "Failed to refresh access token. Please reconnect your account.",
                details={"user_id": str(self.user.id), "error": str(e)},
            )

        # Encrypt and persist new access token
        new_access_token_enc = self._encryption.encrypt(token_data["access_token"])
        oauth_token.access_token_enc = new_access_token_enc
        oauth_token.expires_at = self._oauth_service.calculate_expires_at(token_data["expires_in"])
        if token_data.get("scope"):
            oauth_token.scopes = token_data["scope"].split()

        await self.db.commit()
        await self.db.refresh(oauth_token)

        return token_data["access_token"]

    async def _get_valid_access_token(self) -> str:
        """Get a valid access token, refreshing if necessary."""
        oauth_token = await self._get_oauth_token()

        # Decrypt current access token
        try:
            access_token = self._encryption.decrypt(oauth_token.access_token_enc)
        except (ValueError, InvalidTag) as e:
            raise GoogleCalendarTokenError(
                "Failed to decrypt access token. Please reconnect your account.",
                details={"user_id": str(self.user.id), "error": str(e)},
            )

        # Check if token needs refresh
        if self._is_token_expired_or_expiring(oauth_token.expires_at):
            access_token = await self._refresh_access_token(oauth_token)

        return access_token

    def _build_calendar_client(self, access_token: str):
        """Build an authenticated Google Calendar API client."""
        credentials = Credentials(token=access_token)
        return build("calendar", "v3", credentials=credentials, cache_discovery=False)

    async def _execute_with_token_retry(self, api_call):
        """Execute an API call with automatic token refresh on 401."""
        access_token = await self._get_valid_access_token()
        client = self._build_calendar_client(access_token)

        try:
            # googleapiclient is synchronous. Run it in a worker so requests do
            # not block FastAPI's event loop while waiting on Google's API.
            return await asyncio.to_thread(api_call, client)
        except HttpError as e:
            if e.resp.status == 401:
                # Token might have been revoked or expired, try refresh once
                oauth_token = await self._get_oauth_token()
                access_token = await self._refresh_access_token(oauth_token)
                client = self._build_calendar_client(access_token)
                return await asyncio.to_thread(api_call, client)
            elif e.resp.status == 403:
                raise GoogleCalendarTokenError(
                    "Access denied. Your Google Calendar authorization may have been revoked.",
                    details={"user_id": str(self.user.id), "status": 403},
                )
            elif e.resp.status == 429:
                raise GoogleCalendarRateLimitError(
                    "Google Calendar API rate limit exceeded. Please try again later.",
                    details={"user_id": str(self.user.id), "status": 429},
                )
            raise GoogleCalendarError(
                f"Google Calendar API error: {e.resp.status}",
                details={"user_id": str(self.user.id), "status": e.resp.status, "error": str(e)},
            )

    async def list_events(
        self,
        time_min: datetime | None = None,
        time_max: datetime | None = None,
        max_results: int = 20,
        calendar_id: str = "all",
    ) -> list[dict]:
        """List events from one calendar or every accessible calendar."""
        if time_min is None:
            time_min = datetime.now(UTC)
        if time_max is None:
            time_max = time_min + timedelta(days=7)

        def _call(client):
            events_result = client.events().list(
                calendarId=calendar_id,
                timeMin=time_min.isoformat(),
                timeMax=time_max.isoformat(),
                maxResults=max_results,
                singleEvents=True,
                orderBy="startTime",
            ).execute()
            return events_result.get("items", [])

        events = await self._execute_with_token_retry(_call)

        # Normalize event data
        normalized = []
        for event in events:
            start = event.get("start", {})
            end = event.get("end", {})
            normalized.append({
                "id": event.get("id"),
                "summary": event.get("summary"),
                "description": event.get("description"),
                "location": event.get("location"),
                "start": {
                    "date_time": start.get("dateTime"),
                    "date": start.get("date"),
                    "timezone": start.get("timeZone"),
                },
                "end": {
                    "date_time": end.get("dateTime"),
                    "date": end.get("date"),
                    "timezone": end.get("timeZone"),
                },
                "status": event.get("status"),
                "html_link": event.get("htmlLink"),
                "creator": event.get("creator"),
                "organizer": event.get("organizer"),
                "recurring_event_id": event.get("recurringEventId"),
            })
        return normalized

    async def get_event(
        self,
        event_id: str,
        calendar_id: str = "primary",
    ) -> dict:
        """Get details of a specific calendar event."""
        def _call(client):
            return client.events().get(calendarId=calendar_id, eventId=event_id).execute()

        event = await self._execute_with_token_retry(_call)

        start = event.get("start", {})
        end = event.get("end", {})
        return {
            "id": event.get("id"),
            "summary": event.get("summary"),
            "description": event.get("description"),
            "location": event.get("location"),
            "start": {
                "date_time": start.get("dateTime"),
                "date": start.get("date"),
                "timezone": start.get("timeZone"),
            },
            "end": {
                "date_time": end.get("dateTime"),
                "date": end.get("date"),
                "timezone": end.get("timeZone"),
            },
            "status": event.get("status"),
            "html_link": event.get("htmlLink"),
            "creator": event.get("creator"),
            "organizer": event.get("organizer"),
            "attendees": event.get("attendees"),
            "recurrence": event.get("recurrence"),
            "recurring_event_id": event.get("recurringEventId"),
            "transparency": event.get("transparency"),
            "visibility": event.get("visibility"),
        }

    async def find_free_time(
        self,
        time_min: datetime,
        time_max: datetime,
        duration_minutes: int = 30,
        calendar_id: str = "primary",
    ) -> list[dict]:
        """Find free time slots in the calendar."""
        def _call(client):
            # Use freebusy query to get busy periods
            body = {
                "timeMin": time_min.isoformat(),
                "timeMax": time_max.isoformat(),
                "timeZone": str(time_min.tzinfo) if time_min.tzinfo else "UTC",
                "items": [{"id": calendar_id}],
            }
            return client.freebusy().query(body=body).execute()

        result = await self._execute_with_token_retry(_call)

        calendars = result.get("calendars", {})
        busy_periods = calendars.get(calendar_id, {}).get("busy", [])

        # Convert busy periods to free slots
        free_slots = []
        current = time_min

        for busy in busy_periods:
            busy_start = datetime.fromisoformat(busy["start"])
            busy_end = datetime.fromisoformat(busy["end"])

            if current < busy_start:
                gap_minutes = (busy_start - current).total_seconds() / 60
                if gap_minutes >= duration_minutes:
                    free_slots.append({
                        "start": current.isoformat(),
                        "end": busy_start.isoformat(),
                        "duration_minutes": int(gap_minutes),
                    })

            current = max(current, busy_end)

        # Check for free time after last busy period
        if current < time_max:
            gap_minutes = (time_max - current).total_seconds() / 60
            if gap_minutes >= duration_minutes:
                free_slots.append({
                    "start": current.isoformat(),
                    "end": time_max.isoformat(),
                    "duration_minutes": int(gap_minutes),
                })

        return free_slots


def get_google_calendar_service(db: AsyncSession, user: User) -> GoogleCalendarService:
    """Factory function to get GoogleCalendarService instance."""
    return GoogleCalendarService(db, user)