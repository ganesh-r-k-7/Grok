"""Calendar Tools for AI Integration."""

from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.services.google_calendar import (
    GoogleCalendarError,
    GoogleCalendarNotConnectedError,
    GoogleCalendarRateLimitError,
    GoogleCalendarTokenError,
    get_google_calendar_service,
)
from app.utils.errors import NotFoundError


class CalendarTools:
    """Controlled tools for AI to interact with Google Calendar (read-only)."""

    def __init__(self, db: AsyncSession, user: User):
        self.db = db
        self.user = user
        self._calendar_service = get_google_calendar_service(db, user)

    async def list_events(
        self,
        time_min: datetime | None = None,
        time_max: datetime | None = None,
        max_results: int = 20,
        calendar_id: str = "primary",
    ) -> list[dict]:
        """List calendar events for a date range."""
        try:
            return await self._calendar_service.list_events(
                time_min=time_min,
                time_max=time_max,
                max_results=max_results,
                calendar_id=calendar_id,
            )
        except GoogleCalendarNotConnectedError as e:
            raise NotFoundError("Google Calendar connection", str(e))
        except GoogleCalendarTokenError as e:
            raise NotFoundError("Google Calendar credentials", str(e))
        except GoogleCalendarRateLimitError as e:
            raise NotFoundError("Google Calendar rate limit", str(e))
        except GoogleCalendarError as e:
            raise NotFoundError("Google Calendar", str(e))

    async def get_event(
        self,
        event_id: str,
        calendar_id: str = "primary",
    ) -> dict:
        """Get details of a specific calendar event."""
        try:
            return await self._calendar_service.get_event(
                event_id=event_id,
                calendar_id=calendar_id,
            )
        except GoogleCalendarNotConnectedError as e:
            raise NotFoundError("Google Calendar connection", str(e))
        except GoogleCalendarTokenError as e:
            raise NotFoundError("Google Calendar credentials", str(e))
        except GoogleCalendarRateLimitError as e:
            raise NotFoundError("Google Calendar rate limit", str(e))
        except GoogleCalendarError as e:
            raise NotFoundError("Google Calendar", str(e))

    async def find_free_time(
        self,
        time_min: datetime,
        time_max: datetime,
        duration_minutes: int = 30,
        calendar_id: str = "primary",
    ) -> list[dict]:
        """Find free time slots in the calendar."""
        try:
            return await self._calendar_service.find_free_time(
                time_min=time_min,
                time_max=time_max,
                duration_minutes=duration_minutes,
                calendar_id=calendar_id,
            )
        except GoogleCalendarNotConnectedError as e:
            raise NotFoundError("Google Calendar connection", str(e))
        except GoogleCalendarTokenError as e:
            raise NotFoundError("Google Calendar credentials", str(e))
        except GoogleCalendarRateLimitError as e:
            raise NotFoundError("Google Calendar rate limit", str(e))
        except GoogleCalendarError as e:
            raise NotFoundError("Google Calendar", str(e))

    def get_tool_definitions(self) -> list[dict]:
        """Get tool definitions for AI provider."""
        return [
            {
                "type": "function",
                "function": {
                    "name": "calendar_list_events",
                    "description": "List calendar events for a date range (read-only)",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "time_min": {
                                "type": "string",
                                "format": "date-time",
                                "description": "Start of time range in ISO 8601 format (default: now)",
                            },
                            "time_max": {
                                "type": "string",
                                "format": "date-time",
                                "description": "End of time range in ISO 8601 format (default: 7 days from now)",
                            },
                            "max_results": {
                                "type": "integer",
                                "minimum": 1,
                                "maximum": 100,
                                "default": 20,
                                "description": "Maximum number of events to return",
                            },
                            "calendar_id": {
                                "type": "string",
                                "default": "primary",
                                "description": "Calendar ID to query (default: primary)",
                            },
                        },
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "calendar_get_event",
                    "description": "Get details of a specific calendar event (read-only)",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "event_id": {
                                "type": "string",
                                "description": "Google Calendar event ID (required)",
                            },
                            "calendar_id": {
                                "type": "string",
                                "default": "primary",
                                "description": "Calendar ID (default: primary)",
                            },
                        },
                        "required": ["event_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "calendar_find_free_time",
                    "description": "Find free time slots in the calendar (read-only)",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "time_min": {
                                "type": "string",
                                "format": "date-time",
                                "description": "Start of time range in ISO 8601 format (required)",
                            },
                            "time_max": {
                                "type": "string",
                                "format": "date-time",
                                "description": "End of time range in ISO 8601 format (required)",
                            },
                            "duration_minutes": {
                                "type": "integer",
                                "minimum": 15,
                                "maximum": 480,
                                "default": 30,
                                "description": "Minimum duration of free slot in minutes",
                            },
                            "calendar_id": {
                                "type": "string",
                                "default": "primary",
                                "description": "Calendar ID to query (default: primary)",
                            },
                        },
                        "required": ["time_min", "time_max"],
                    },
                },
            },
        ]

    async def execute_tool(self, tool_name: str, arguments: dict) -> dict:
        """Execute a tool by name with arguments."""
        if tool_name == "calendar_list_events":
            # Parse datetime strings if provided
            time_min = None
            time_max = None
            if arguments.get("time_min"):
                time_min = datetime.fromisoformat(arguments["time_min"])
            if arguments.get("time_max"):
                time_max = datetime.fromisoformat(arguments["time_max"])

            events = await self.list_events(
                time_min=time_min,
                time_max=time_max,
                max_results=arguments.get("max_results", 20),
                calendar_id=arguments.get("calendar_id", "primary"),
            )
            return {"success": True, "events": events, "count": len(events)}

        elif tool_name == "calendar_get_event":
            event = await self.get_event(
                event_id=arguments["event_id"],
                calendar_id=arguments.get("calendar_id", "primary"),
            )
            return {"success": True, "event": event}

        elif tool_name == "calendar_find_free_time":
            time_min = datetime.fromisoformat(arguments["time_min"])
            time_max = datetime.fromisoformat(arguments["time_max"])

            free_slots = await self.find_free_time(
                time_min=time_min,
                time_max=time_max,
                duration_minutes=arguments.get("duration_minutes", 30),
                calendar_id=arguments.get("calendar_id", "primary"),
            )
            return {"success": True, "free_slots": free_slots, "count": len(free_slots)}

        else:
            return {"success": False, "error": f"Unknown calendar tool: {tool_name}"}