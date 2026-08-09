"""Notification tasks - placeholder for Phase 1+ implementation."""

from app.tasks.celery_app import celery_app


@celery_app.task(name="notifications.event_reminders")
def check_event_reminders_task():
    """Check for upcoming events and send reminders."""
    # Phase 1: Implement event reminders
    pass


@celery_app.task(name="notifications.task_due")
def check_task_due_dates_task():
    """Check for due/overdue tasks and send notifications."""
    # Phase 1: Implement task due notifications
    pass


@celery_app.task(name="notifications.morning_briefing")
def send_morning_briefing_task(user_id: str):
    """Send morning briefing to a user."""
    # Phase 1: Implement morning briefing
    pass