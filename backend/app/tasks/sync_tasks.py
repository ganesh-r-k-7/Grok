"""Sync tasks - placeholder for Phase 1+ implementation."""

from app.tasks.celery_app import celery_app


@celery_app.task(name="sync.gmail")
def sync_gmail_task(user_id: str):
    """Sync Gmail messages for a user."""
    # Phase 1: Implement Gmail sync
    pass


@celery_app.task(name="sync.calendar")
def sync_calendar_task(user_id: str):
    """Sync Calendar events for a user."""
    # Phase 1: Implement Calendar sync
    pass


@celery_app.task(name="sync.tasks")
def sync_tasks_task(user_id: str):
    """Sync Tasks for a user."""
    # Phase 1: Implement Tasks sync
    pass