"""Task Tools for AI Integration."""

from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.task import Task, TaskStatus, TaskPriority
from app.models.user import User
from app.utils.errors import NotFoundError


class TaskTools:
    """Controlled tools for AI to interact with tasks."""

    def __init__(self, db: AsyncSession, user: User):
        self.db = db
        self.user = user

    async def create_task(
        self,
        title: str,
        description: Optional[str] = None,
        status: TaskStatus = TaskStatus.TODO,
        priority: TaskPriority = TaskPriority.MEDIUM,
        due_at: Optional[datetime] = None,
    ) -> Task:
        """Create a new task for the user."""
        task = Task(
            user_id=self.user.id,
            title=title,
            description=description,
            status=status,
            priority=priority,
            due_at=due_at,
        )
        self.db.add(task)
        await self.db.commit()
        await self.db.refresh(task)
        return task

    async def list_tasks(
        self,
        status: Optional[TaskStatus] = None,
        priority: Optional[TaskPriority] = None,
        overdue: Optional[bool] = None,
        due_before: Optional[datetime] = None,
        due_after: Optional[datetime] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Task], int]:
        """List tasks for the user with filtering and pagination."""
        from sqlalchemy import func

        query = select(Task).where(Task.user_id == self.user.id)

        if status:
            query = query.where(Task.status == status)
        if priority:
            query = query.where(Task.priority == priority)
        if overdue is not None:
            now = datetime.now(timezone.utc)
            if overdue:
                query = query.where(Task.due_at < now, Task.status != TaskStatus.COMPLETED)
            else:
                query = query.where(
                    (Task.due_at >= now) | (Task.due_at.is_(None)) | (Task.status == TaskStatus.COMPLETED)
                )
        if due_before:
            query = query.where(Task.due_at <= due_before)
        if due_after:
            query = query.where(Task.due_at >= due_after)

        # Count total
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self.db.execute(count_query)
        total = total_result.scalar_one()

        # Apply pagination and ordering
        query = query.order_by(Task.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
        result = await self.db.execute(query)
        tasks = result.scalars().all()

        return list(tasks), total

    async def get_task(self, task_id: UUID) -> Task:
        """Get a specific task by ID (must belong to user)."""
        result = await self.db.execute(
            select(Task).where(Task.id == task_id, Task.user_id == self.user.id)
        )
        task = result.scalar_one_or_none()

        if not task:
            raise NotFoundError("Task", str(task_id))

        return task

    async def update_task(
        self,
        task_id: UUID,
        title: Optional[str] = None,
        description: Optional[str] = None,
        status: Optional[TaskStatus] = None,
        priority: Optional[TaskPriority] = None,
        due_at: Optional[datetime] = None,
    ) -> Task:
        """Update a task (must belong to user)."""
        task = await self.get_task(task_id)

        old_status = task.status

        if title is not None:
            task.title = title
        if description is not None:
            task.description = description
        if status is not None:
            task.status = status
            # Handle completed_at logic
            if status == TaskStatus.COMPLETED and old_status != TaskStatus.COMPLETED:
                task.completed_at = datetime.now(timezone.utc)
            elif status != TaskStatus.COMPLETED and old_status == TaskStatus.COMPLETED:
                task.completed_at = None
        if priority is not None:
            task.priority = priority
        if due_at is not None:
            task.due_at = due_at

        await self.db.commit()
        await self.db.refresh(task)
        return task

    async def delete_task(self, task_id: UUID) -> None:
        """Delete a task (must belong to user)."""
        task = await self.get_task(task_id)
        await self.db.delete(task)
        await self.db.commit()

    def get_tool_definitions(self) -> list[dict]:
        """Get tool definitions for AI provider."""
        return [
            {
                "type": "function",
                "function": {
                    "name": "create_task",
                    "description": "Create a new task for the user",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "title": {"type": "string", "description": "Task title (required)"},
                            "description": {"type": "string", "description": "Task description"},
                            "status": {
                                "type": "string",
                                "enum": ["todo", "in_progress", "completed"],
                                "description": "Task status",
                            },
                            "priority": {
                                "type": "string",
                                "enum": ["low", "medium", "high", "urgent"],
                                "description": "Task priority",
                            },
                            "due_at": {
                                "type": "string",
                                "format": "date-time",
                                "description": "Due date in ISO 8601 format",
                            },
                        },
                        "required": ["title"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "list_tasks",
                    "description": "List tasks for the user with optional filtering",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "status": {"type": "string", "enum": ["todo", "in_progress", "completed"]},
                            "priority": {"type": "string", "enum": ["low", "medium", "high", "urgent"]},
                            "overdue": {"type": "boolean"},
                            "due_before": {"type": "string", "format": "date-time"},
                            "due_after": {"type": "string", "format": "date-time"},
                            "page": {"type": "integer", "minimum": 1, "default": 1},
                            "page_size": {"type": "integer", "minimum": 1, "maximum": 100, "default": 20},
                        },
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "get_task",
                    "description": "Get a specific task by ID",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "task_id": {"type": "string", "format": "uuid"},
                        },
                        "required": ["task_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "update_task",
                    "description": "Update a task",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "task_id": {"type": "string", "format": "uuid"},
                            "title": {"type": "string"},
                            "description": {"type": "string"},
                            "status": {"type": "string", "enum": ["todo", "in_progress", "completed"]},
                            "priority": {"type": "string", "enum": ["low", "medium", "high", "urgent"]},
                            "due_at": {"type": "string", "format": "date-time"},
                        },
                        "required": ["task_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "delete_task",
                    "description": "Delete a task (use with caution)",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "task_id": {"type": "string", "format": "uuid"},
                        },
                        "required": ["task_id"],
                    },
                },
            },
        ]

    async def execute_tool(self, tool_name: str, arguments: dict) -> dict:
        """Execute a tool by name with arguments."""
        if tool_name == "create_task":
            task = await self.create_task(**arguments)
            return {"success": True, "task": {"id": str(task.id), "title": task.title, "status": task.status.value}}
        elif tool_name == "list_tasks":
            tasks, total = await self.list_tasks(**arguments)
            return {
                "success": True,
                "tasks": [
                    {
                        "id": str(t.id),
                        "title": t.title,
                        "status": t.status.value,
                        "priority": t.priority.value,
                        "due_at": t.due_at.isoformat() if t.due_at else None,
                    }
                    for t in tasks
                ],
                "total": total,
            }
        elif tool_name == "get_task":
            task = await self.get_task(arguments["task_id"])
            return {
                "success": True,
                "task": {
                    "id": str(task.id),
                    "title": task.title,
                    "description": task.description,
                    "status": task.status.value,
                    "priority": task.priority.value,
                    "due_at": task.due_at.isoformat() if task.due_at else None,
                    "completed_at": task.completed_at.isoformat() if task.completed_at else None,
                },
            }
        elif tool_name == "update_task":
            task_id = arguments.pop("task_id")
            task = await self.update_task(task_id, **arguments)
            return {"success": True, "task": {"id": str(task.id), "title": task.title, "status": task.status.value}}
        elif tool_name == "delete_task":
            await self.delete_task(arguments["task_id"])
            return {"success": True, "message": "Task deleted"}
        else:
            return {"success": False, "error": f"Unknown tool: {tool_name}"}