import pytest
from httpx import AsyncClient
from uuid import uuid4
from datetime import datetime, timezone, timedelta
from app.models.user import User
from app.models.task import Task, TaskStatus, TaskPriority
from app.utils.security import hash_password


def unique_email(prefix: str = "test") -> str:
    """Generate a unique email for testing."""
    return f"{prefix}_{uuid4().hex[:8]}@example.com"


@pytest.fixture
async def authenticated_user(client: AsyncClient, db_session):
    """Create and return an authenticated user with cookies."""
    email = unique_email("taskuser")
    user = User(
        email=email,
        password_hash=hash_password("password123"),
        name="Task User",
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    login_response = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "password123"},
    )
    assert login_response.status_code == 200
    cookies = login_response.cookies
    return user, cookies


@pytest.fixture
async def sample_tasks(db_session, authenticated_user):
    """Create sample tasks for testing."""
    user, _ = authenticated_user
    tasks = [
        Task(
            user_id=user.id,
            title="Task 1",
            description="Description 1",
            status=TaskStatus.TODO,
            priority=TaskPriority.HIGH,
            due_at=datetime.now(timezone.utc) + timedelta(days=1),
        ),
        Task(
            user_id=user.id,
            title="Task 2",
            description="Description 2",
            status=TaskStatus.IN_PROGRESS,
            priority=TaskPriority.MEDIUM,
            due_at=datetime.now(timezone.utc) + timedelta(days=2),
        ),
        Task(
            user_id=user.id,
            title="Task 3",
            description="Description 3",
            status=TaskStatus.COMPLETED,
            priority=TaskPriority.LOW,
            completed_at=datetime.now(timezone.utc),
        ),
        Task(
            user_id=user.id,
            title="Overdue Task",
            description="This is overdue",
            status=TaskStatus.TODO,
            priority=TaskPriority.URGENT,
            due_at=datetime.now(timezone.utc) - timedelta(days=1),
        ),
    ]
    db_session.add_all(tasks)
    await db_session.commit()
    for task in tasks:
        await db_session.refresh(task)
    return tasks


class TestTaskList:
    @pytest.mark.asyncio
    async def test_list_tasks_success(self, client: AsyncClient, authenticated_user, sample_tasks):
        """Test listing tasks for authenticated user."""
        user, cookies = authenticated_user
        response = await client.get("/api/v1/tasks", cookies=cookies)
        assert response.status_code == 200
        data = response.json()
        assert "tasks" in data
        assert len(data["tasks"]) == 4
        assert data["total"] == 4
        assert data["page"] == 1
        assert data["page_size"] == 20

    @pytest.mark.asyncio
    async def test_list_tasks_empty(self, client: AsyncClient, authenticated_user):
        """Test listing tasks when user has no tasks."""
        user, cookies = authenticated_user
        response = await client.get("/api/v1/tasks", cookies=cookies)
        assert response.status_code == 200
        data = response.json()
        assert data["tasks"] == []
        assert data["total"] == 0

    @pytest.mark.asyncio
    async def test_list_tasks_unauthorized(self, client: AsyncClient):
        """Test listing tasks without authentication fails."""
        response = await client.get("/api/v1/tasks")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_list_tasks_filter_status(self, client: AsyncClient, authenticated_user, sample_tasks):
        """Test filtering tasks by status."""
        user, cookies = authenticated_user
        response = await client.get("/api/v1/tasks?status=completed", cookies=cookies)
        assert response.status_code == 200
        data = response.json()
        assert len(data["tasks"]) == 1
        assert data["tasks"][0]["status"] == "completed"

    @pytest.mark.asyncio
    async def test_list_tasks_filter_priority(self, client: AsyncClient, authenticated_user, sample_tasks):
        """Test filtering tasks by priority."""
        user, cookies = authenticated_user
        response = await client.get("/api/v1/tasks?priority=high", cookies=cookies)
        assert response.status_code == 200
        data = response.json()
        assert len(data["tasks"]) == 1
        assert data["tasks"][0]["priority"] == "high"

    @pytest.mark.asyncio
    async def test_list_tasks_filter_overdue(self, client: AsyncClient, authenticated_user, sample_tasks):
        """Test filtering overdue tasks."""
        user, cookies = authenticated_user
        response = await client.get("/api/v1/tasks?overdue=true", cookies=cookies)
        assert response.status_code == 200
        data = response.json()
        assert len(data["tasks"]) == 1
        assert data["tasks"][0]["title"] == "Overdue Task"

    @pytest.mark.asyncio
    async def test_list_tasks_pagination(self, client: AsyncClient, authenticated_user, sample_tasks):
        """Test pagination of tasks."""
        user, cookies = authenticated_user
        response = await client.get("/api/v1/tasks?page=1&page_size=2", cookies=cookies)
        assert response.status_code == 200
        data = response.json()
        assert len(data["tasks"]) == 2
        assert data["page"] == 1
        assert data["page_size"] == 2
        assert data["total_pages"] == 2

    @pytest.mark.asyncio
    async def test_list_tasks_due_before_after(self, client: AsyncClient, authenticated_user, sample_tasks):
        """Test filtering tasks by due date range."""
        user, cookies = authenticated_user
        future_date = (datetime.now(timezone.utc) + timedelta(days=3)).strftime("%Y-%m-%dT%H:%M:%S")
        response = await client.get(f"/api/v1/tasks?due_before={future_date}", cookies=cookies)
        assert response.status_code == 200
        data = response.json()
        assert len(data["tasks"]) >= 3


class TestTaskCreate:
    @pytest.mark.asyncio
    async def test_create_task_success(self, client: AsyncClient, authenticated_user):
        """Test creating a new task."""
        user, cookies = authenticated_user
        response = await client.post(
            "/api/v1/tasks",
            json={
                "title": "New Task",
                "description": "Task description",
                "status": "todo",
                "priority": "high",
                "due_at": (datetime.now(timezone.utc) + timedelta(days=1)).isoformat(),
            },
            cookies=cookies,
        )
        assert response.status_code == 201
        data = response.json()
        assert data["title"] == "New Task"
        assert data["description"] == "Task description"
        assert data["status"] == "todo"
        assert data["priority"] == "high"
        assert data["user_id"] == str(user.id)
        assert "id" in data
        assert "created_at" in data
        assert "updated_at" in data

    @pytest.mark.asyncio
    async def test_create_task_minimal(self, client: AsyncClient, authenticated_user):
        """Test creating a task with only required fields."""
        user, cookies = authenticated_user
        response = await client.post(
            "/api/v1/tasks",
            json={"title": "Minimal Task"},
            cookies=cookies,
        )
        assert response.status_code == 201
        data = response.json()
        assert data["title"] == "Minimal Task"
        assert data["status"] == "todo"
        assert data["priority"] == "medium"
        assert data["description"] is None
        assert data["due_at"] is None

    @pytest.mark.asyncio
    async def test_create_task_unauthorized(self, client: AsyncClient):
        """Test creating a task without authentication fails."""
        response = await client.post(
            "/api/v1/tasks",
            json={"title": "Unauthorized Task"},
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_create_task_invalid_title(self, client: AsyncClient, authenticated_user):
        """Test creating a task with empty title fails."""
        user, cookies = authenticated_user
        response = await client.post(
            "/api/v1/tasks",
            json={"title": ""},
            cookies=cookies,
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_create_task_title_too_long(self, client: AsyncClient, authenticated_user):
        """Test creating a task with title too long fails."""
        user, cookies = authenticated_user
        response = await client.post(
            "/api/v1/tasks",
            json={"title": "a" * 256},
            cookies=cookies,
        )
        assert response.status_code == 422


class TestTaskGet:
    @pytest.mark.asyncio
    async def test_get_task_success(self, client: AsyncClient, authenticated_user, sample_tasks):
        """Test getting a specific task."""
        user, cookies = authenticated_user
        task = sample_tasks[0]
        response = await client.get(f"/api/v1/tasks/{task.id}", cookies=cookies)
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(task.id)
        assert data["title"] == task.title

    @pytest.mark.asyncio
    async def test_get_task_not_found(self, client: AsyncClient, authenticated_user):
        """Test getting a non-existent task returns 404."""
        user, cookies = authenticated_user
        response = await client.get(f"/api/v1/tasks/{uuid4()}", cookies=cookies)
        assert response.status_code == 404
        data = response.json()
        assert data["type"] == "https://grok.dev/errors/not_found"

    @pytest.mark.asyncio
    async def test_get_task_other_user(self, client: AsyncClient, authenticated_user, db_session):
        """Test getting another user's task returns 404."""
        user, cookies = authenticated_user
        # Create another user and their task
        other_email = unique_email("other")
        other_user = User(
            email=other_email,
            password_hash=hash_password("password123"),
            name="Other User",
        )
        db_session.add(other_user)
        await db_session.commit()
        await db_session.refresh(other_user)

        other_task = Task(
            user_id=other_user.id,
            title="Other User Task",
            status=TaskStatus.TODO,
        )
        db_session.add(other_task)
        await db_session.commit()
        await db_session.refresh(other_task)

        response = await client.get(f"/api/v1/tasks/{other_task.id}", cookies=cookies)
        assert response.status_code == 404


class TestTaskUpdate:
    @pytest.mark.asyncio
    async def test_update_task_success(self, client: AsyncClient, authenticated_user, sample_tasks):
        """Test updating a task."""
        user, cookies = authenticated_user
        task = sample_tasks[0]
        response = await client.patch(
            f"/api/v1/tasks/{task.id}",
            json={
                "title": "Updated Title",
                "status": "in_progress",
                "priority": "urgent",
            },
            cookies=cookies,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "Updated Title"
        assert data["status"] == "in_progress"
        assert data["priority"] == "urgent"

    @pytest.mark.asyncio
    async def test_update_task_status_to_completed(self, client: AsyncClient, authenticated_user, sample_tasks):
        """Test updating task status to completed sets completed_at."""
        user, cookies = authenticated_user
        task = sample_tasks[0]  # TODO task
        response = await client.patch(
            f"/api/v1/tasks/{task.id}",
            json={"status": "completed"},
            cookies=cookies,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "completed"
        assert data["completed_at"] is not None

    @pytest.mark.asyncio
    async def test_update_task_status_from_completed(self, client: AsyncClient, authenticated_user, sample_tasks):
        """Test updating task status from completed clears completed_at."""
        user, cookies = authenticated_user
        task = sample_tasks[2]  # COMPLETED task
        response = await client.patch(
            f"/api/v1/tasks/{task.id}",
            json={"status": "todo"},
            cookies=cookies,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "todo"
        assert data["completed_at"] is None

    @pytest.mark.asyncio
    async def test_update_task_partial(self, client: AsyncClient, authenticated_user, sample_tasks):
        """Test partial update of a task."""
        user, cookies = authenticated_user
        task = sample_tasks[0]
        response = await client.patch(
            f"/api/v1/tasks/{task.id}",
            json={"description": "Updated description only"},
            cookies=cookies,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["description"] == "Updated description only"
        assert data["title"] == task.title  # unchanged

    @pytest.mark.asyncio
    async def test_update_task_not_found(self, client: AsyncClient, authenticated_user):
        """Test updating a non-existent task returns 404."""
        user, cookies = authenticated_user
        response = await client.patch(
            f"/api/v1/tasks/{uuid4()}",
            json={"title": "Updated"},
            cookies=cookies,
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_update_task_other_user(self, client: AsyncClient, authenticated_user, db_session):
        """Test updating another user's task returns 404."""
        user, cookies = authenticated_user
        other_email = unique_email("other")
        other_user = User(
            email=other_email,
            password_hash=hash_password("password123"),
        )
        db_session.add(other_user)
        await db_session.commit()
        await db_session.refresh(other_user)

        other_task = Task(
            user_id=other_user.id,
            title="Other User Task",
            status=TaskStatus.TODO,
        )
        db_session.add(other_task)
        await db_session.commit()
        await db_session.refresh(other_task)

        response = await client.patch(
            f"/api/v1/tasks/{other_task.id}",
            json={"title": "Hacked"},
            cookies=cookies,
        )
        assert response.status_code == 404


class TestTaskDelete:
    @pytest.mark.asyncio
    async def test_delete_task_success(self, client: AsyncClient, authenticated_user, sample_tasks):
        """Test deleting a task."""
        user, cookies = authenticated_user
        task = sample_tasks[0]
        response = await client.delete(f"/api/v1/tasks/{task.id}", cookies=cookies)
        assert response.status_code == 204

        # Verify task is deleted
        response = await client.get(f"/api/v1/tasks/{task.id}", cookies=cookies)
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_task_not_found(self, client: AsyncClient, authenticated_user):
        """Test deleting a non-existent task returns 404."""
        user, cookies = authenticated_user
        response = await client.delete(f"/api/v1/tasks/{uuid4()}", cookies=cookies)
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_task_other_user(self, client: AsyncClient, authenticated_user, db_session):
        """Test deleting another user's task returns 404."""
        user, cookies = authenticated_user
        other_email = unique_email("other")
        other_user = User(
            email=other_email,
            password_hash=hash_password("password123"),
        )
        db_session.add(other_user)
        await db_session.commit()
        await db_session.refresh(other_user)

        other_task = Task(
            user_id=other_user.id,
            title="Other User Task",
            status=TaskStatus.TODO,
        )
        db_session.add(other_task)
        await db_session.commit()
        await db_session.refresh(other_task)

        response = await client.delete(f"/api/v1/tasks/{other_task.id}", cookies=cookies)
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_task_unauthorized(self, client: AsyncClient):
        """Test deleting a task without authentication fails."""
        response = await client.delete(f"/api/v1/tasks/{uuid4()}")
        assert response.status_code == 401


class TestTaskOwnership:
    @pytest.mark.asyncio
    async def test_tasks_isolated_by_user(self, client: AsyncClient, db_session):
        """Test that users can only see their own tasks."""
        # Create two users
        email1 = unique_email("user1")
        user1 = User(email=email1, password_hash=hash_password("password123"))
        email2 = unique_email("user2")
        user2 = User(email=email2, password_hash=hash_password("password123"))
        db_session.add_all([user1, user2])
        await db_session.commit()
        await db_session.refresh(user1)
        await db_session.refresh(user2)

        # Create tasks for each user
        task1 = Task(user_id=user1.id, title="User 1 Task", status=TaskStatus.TODO)
        task2 = Task(user_id=user2.id, title="User 2 Task", status=TaskStatus.TODO)
        db_session.add_all([task1, task2])
        await db_session.commit()

        # Login as user1
        login1 = await client.post(
            "/api/v1/auth/login",
            json={"email": email1, "password": "password123"},
        )
        cookies1 = login1.cookies

        # Login as user2
        login2 = await client.post(
            "/api/v1/auth/login",
            json={"email": email2, "password": "password123"},
        )
        cookies2 = login2.cookies

        # User1 should only see their task
        response1 = await client.get("/api/v1/tasks", cookies=cookies1)
        assert response1.status_code == 200
        data1 = response1.json()
        assert len(data1["tasks"]) == 1
        assert data1["tasks"][0]["title"] == "User 1 Task"

        # User2 should only see their task
        response2 = await client.get("/api/v1/tasks", cookies=cookies2)
        assert response2.status_code == 200
        data2 = response2.json()
        assert len(data2["tasks"]) == 1
        assert data2["tasks"][0]["title"] == "User 2 Task"