"""Tests for AI streaming functionality."""

import pytest
from httpx import AsyncClient
from uuid import uuid4
from app.models.user import User
from app.models.conversation import Conversation, Message, ConversationRole
from app.utils.security import hash_password
from app.services.ai_providers.base import ChatChunk
from app.services.ai_providers.mock import MockProvider


def unique_email(prefix: str = "test") -> str:
    """Generate a unique email for testing."""
    return f"{prefix}_{uuid4().hex[:8]}@example.com"


@pytest.fixture
async def authenticated_user(client: AsyncClient, db_session):
    """Create and return an authenticated user with cookies."""
    email = unique_email("aiuser")
    user = User(
        email=email,
        password_hash=hash_password("password123"),
        name="AI User",
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
async def mock_provider_with_content():
    """Create a mock provider that returns content."""
    return MockProvider(responses=[
        {"type": "content", "content": "Hello! How can I help you?"},
    ])


@pytest.fixture
async def mock_provider_with_tool_call():
    """Create a mock provider that returns a tool call then content."""
    return MockProvider(responses=[
        {"type": "tool_call", "tool_call": {
            "id": "call_123",
            "type": "function",
            "function": {"name": "create_task", "arguments": '{"title": "Test Task", "priority": "high"}'}
        }},
        {"type": "content", "content": "I've created the task for you."},
    ])


@pytest.fixture
async def mock_provider_with_error():
    """Create a mock provider that returns an error."""
    return MockProvider(responses=[
        {"type": "error", "error": "Provider is down"},
    ])


class TestChatStream:
    """Tests for the streaming chat endpoint."""

    @pytest.mark.asyncio
    async def test_chat_stream_basic(self, client: AsyncClient, authenticated_user, monkeypatch):
        """Test basic streaming chat response."""
        from app.services.ai_providers.mock import MockProvider
    
        user, cookies = authenticated_user
    
        # Override provider to use mock - patch at the point of use (ai_service module)
        def mock_get_provider(provider_name="mock"):
            return MockProvider(responses=[
                {"type": "content", "content": "Hello! This is a streaming response."},
            ])
    
        monkeypatch.setattr("app.services.ai_service.get_provider", mock_get_provider)
    
        response = await client.post(
            "/api/v1/ai/chat/stream",
            json={"message": "Hello"},
            cookies=cookies,
        )
        assert response.status_code == 200
        assert response.headers["content-type"] == "text/event-stream; charset=utf-8"
    
        # Parse SSE events
        content = response.text
        events = [line for line in content.split("\n") if line.startswith("data: ")]
    
        # Should have content and done events
        assert len(events) >= 2
    
        # Check content event
        content_event = None
        done_events = []
        for event in events:
            data = event[6:]  # Remove "data: "
            if data == "[DONE]":
                continue
            import json
            parsed = json.loads(data)
            if parsed.get("type") == "content":
                content_event = parsed
            elif parsed.get("type") == "done":
                done_events.append(parsed)
    
        assert content_event is not None
        assert "streaming response" in content_event.get("content", "")
        
        # The last done event should be from the API and have conversation_id
        assert len(done_events) >= 1
        final_done = done_events[-1]
        assert "conversation_id" in final_done

    @pytest.mark.asyncio
    async def test_chat_stream_with_conversation_id(self, client: AsyncClient, authenticated_user, db_session, monkeypatch):
        """Test streaming chat with existing conversation."""
        user, cookies = authenticated_user
        
        # Create conversation
        conversation = Conversation(user_id=user.id, title="Test Conversation")
        db_session.add(conversation)
        await db_session.commit()
        await db_session.refresh(conversation)
        
        def mock_get_provider(provider_name="mock"):
            return MockProvider(responses=[
                {"type": "content", "content": "Response in existing conversation."},
            ])
        
        monkeypatch.setattr("app.services.ai_service.get_provider", mock_get_provider)
        
        try:
            response = await client.post(
                "/api/v1/ai/chat/stream",
                json={
                    "message": "Hello",
                    "conversation_id": str(conversation.id),
                },
                cookies=cookies,
            )
            assert response.status_code == 200
            
            content = response.text
            events = [line for line in content.split("\n") if line.startswith("data: ")]
            
            done_event = None
            for event in events:
                data = event[6:]
                if data == "[DONE]":
                    continue
                import json
                parsed = json.loads(data)
                if parsed.get("type") == "done":
                    done_event = parsed
            
            assert done_event is not None
            assert done_event.get("conversation_id") == str(conversation.id)
        finally:
            monkeypatch.setattr("app.services.ai_service.get_provider", mock_get_provider.__wrapped__ if hasattr(mock_get_provider, '__wrapped__') else None)

    @pytest.mark.asyncio
    async def test_chat_stream_creates_conversation(self, client: AsyncClient, authenticated_user, monkeypatch):
        """Test streaming chat creates new conversation when none provided."""
        user, cookies = authenticated_user
        
        def mock_get_provider(provider_name="mock"):
            return MockProvider(responses=[
                {"type": "content", "content": "New conversation response."},
            ])
        
        monkeypatch.setattr("app.services.ai_service.get_provider", mock_get_provider)
        
        try:
            response = await client.post(
                "/api/v1/ai/chat/stream",
                json={"message": "First message"},
                cookies=cookies,
            )
            assert response.status_code == 200
            
            content = response.text
            events = [line for line in content.split("\n") if line.startswith("data: ")]
            
            done_event = None
            for event in events:
                data = event[6:]
                if data == "[DONE]":
                    continue
                import json
                parsed = json.loads(data)
                if parsed.get("type") == "done":
                    done_event = parsed
            
            assert done_event is not None
            assert "conversation_id" in done_event
        finally:
            pass

    @pytest.mark.asyncio
    async def test_chat_stream_unauthorized(self, client: AsyncClient):
        """Test streaming chat without authentication returns 401."""
        response = await client.post(
            "/api/v1/ai/chat/stream",
            json={"message": "Hello"},
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_chat_stream_empty_message(self, client: AsyncClient, authenticated_user):
        """Test streaming chat with empty message returns 422."""
        user, cookies = authenticated_user
        response = await client.post(
            "/api/v1/ai/chat/stream",
            json={"message": ""},
            cookies=cookies,
        )
        assert response.status_code == 422


class TestChatStreamToolCalling:
    """Tests for tool calling in streaming chat."""

    @pytest.mark.asyncio
    async def test_chat_stream_with_tool_call(self, client: AsyncClient, authenticated_user, db_session, monkeypatch):
        """Test streaming chat that invokes a tool."""
        user, cookies = authenticated_user
        
        def mock_get_provider(provider_name="mock"):
            return MockProvider(responses=[
                {"type": "tool_call", "tool_call": {
                    "id": "call_123",
                    "type": "function",
                    "function": {"name": "create_task", "arguments": '{"title": "Test Task", "description": "From AI", "priority": "high"}'}
                }},
                {"type": "content", "content": "I've created the task for you."},
            ])
        
        monkeypatch.setattr("app.services.ai_service.get_provider", mock_get_provider)
        
        try:
            response = await client.post(
                "/api/v1/ai/chat/stream",
                json={"message": "Create a task called Test Task with high priority"},
                cookies=cookies,
            )
            assert response.status_code == 200
            
            content = response.text
            events = [line for line in content.split("\n") if line.startswith("data: ")]
            
            tool_call_event = None
            tool_result_event = None
            content_event = None
            done_event = None
            
            for event in events:
                data = event[6:]
                if data == "[DONE]":
                    continue
                import json
                parsed = json.loads(data)
                if parsed.get("type") == "tool_call":
                    tool_call_event = parsed
                elif parsed.get("type") == "tool_result":
                    tool_result_event = parsed
                elif parsed.get("type") == "content":
                    content_event = parsed
                elif parsed.get("type") == "done":
                    done_event = parsed
            
            assert tool_call_event is not None
            assert tool_call_event.get("tool_call", {}).get("function", {}).get("name") == "create_task"
            
            assert tool_result_event is not None
            assert tool_result_event.get("tool_result", {}).get("success") is True
            
            assert content_event is not None
            assert "created" in content_event.get("content", "").lower()
            
            assert done_event is not None
        finally:
            pass


class TestChatStreamErrorHandling:
    """Tests for error handling in streaming chat."""

    @pytest.mark.asyncio
    async def test_chat_stream_provider_error(self, client: AsyncClient, authenticated_user, monkeypatch):
        """Test streaming chat handles provider errors gracefully."""
        user, cookies = authenticated_user
        
        def mock_get_provider(provider_name="mock"):
            return MockProvider(responses=[
                {"type": "error", "error": "Provider is down"},
            ])
        
        monkeypatch.setattr("app.services.ai_service.get_provider", mock_get_provider)
        
        try:
            response = await client.post(
                "/api/v1/ai/chat/stream",
                json={"message": "Hello"},
                cookies=cookies,
            )
            assert response.status_code == 200
            
            content = response.text
            events = [line for line in content.split("\n") if line.startswith("data: ")]
            
            error_event = None
            done_event = None
            
            for event in events:
                data = event[6:]
                if data == "[DONE]":
                    continue
                import json
                parsed = json.loads(data)
                if parsed.get("type") == "error":
                    error_event = parsed
                elif parsed.get("type") == "done":
                    done_event = parsed
            
            assert error_event is not None
            assert "Provider is down" in error_event.get("error", "")
            
            # Should still send done event
            assert done_event is not None
        finally:
            pass

    @pytest.mark.asyncio
    async def test_chat_stream_nonexistent_conversation(self, client: AsyncClient, authenticated_user, monkeypatch):
        """Test streaming chat with non-existent conversation returns 404."""
        user, cookies = authenticated_user
        
        def mock_get_provider(provider_name="mock"):
            return MockProvider(responses=[
                {"type": "content", "content": "Response"},
            ])
        
        monkeypatch.setattr("app.services.ai_service.get_provider", mock_get_provider)
        
        try:
            response = await client.post(
                "/api/v1/ai/chat/stream",
                json={
                    "message": "Hello",
                    "conversation_id": str(uuid4()),
                },
                cookies=cookies,
            )
            assert response.status_code == 404
        finally:
            pass


class TestChatStreamSSEFormat:
    """Tests for SSE format compliance."""

    @pytest.mark.asyncio
    async def test_chat_stream_sse_format(self, client: AsyncClient, authenticated_user, monkeypatch):
        """Test that streaming response follows SSE format."""
        user, cookies = authenticated_user
        
        def mock_get_provider(provider_name="mock"):
            return MockProvider(responses=[
                {"type": "content", "content": "Hello"},
                {"type": "content", "content": " world"},
            ])
        
        monkeypatch.setattr("app.services.ai_service.get_provider", mock_get_provider)
        
        try:
            response = await client.post(
                "/api/v1/ai/chat/stream",
                json={"message": "Hi"},
                cookies=cookies,
            )
            assert response.status_code == 200
            
            content = response.text
            lines = content.split("\n")
            
            # Check SSE format: each event starts with "data: " and ends with "\n\n"
            data_lines = [line for line in lines if line.startswith("data: ")]
            assert len(data_lines) >= 2
            
            # Each data line should be valid JSON
            import json
            for line in data_lines:
                data = line[6:]
                if data == "[DONE]":
                    continue
                parsed = json.loads(data)
                assert "type" in parsed
        finally:
            pass

    @pytest.mark.asyncio
    async def test_chat_stream_headers(self, client: AsyncClient, authenticated_user, monkeypatch):
        """Test that streaming response has correct headers."""
        user, cookies = authenticated_user
        
        def mock_get_provider(provider_name="mock"):
            return MockProvider(responses=[
                {"type": "content", "content": "Hello"},
            ])
        
        monkeypatch.setattr("app.services.ai_service.get_provider", mock_get_provider)
        
        try:
            response = await client.post(
                "/api/v1/ai/chat/stream",
                json={"message": "Hi"},
                cookies=cookies,
            )
            assert response.status_code == 200
            assert response.headers["content-type"] == "text/event-stream; charset=utf-8"
            assert response.headers["cache-control"] == "no-cache"
            assert response.headers["connection"] == "keep-alive"
        finally:
            pass


class TestChatStreamPersistence:
    """Tests for message persistence in streaming chat."""

    @pytest.mark.asyncio
    async def test_chat_stream_saves_messages(self, client: AsyncClient, authenticated_user, db_session, monkeypatch):
        """Test that streaming chat saves user and assistant messages."""
        user, cookies = authenticated_user
        
        def mock_get_provider(provider_name="mock"):
            return MockProvider(responses=[
                {"type": "content", "content": "This is the assistant response."},
            ])
        
        monkeypatch.setattr("app.services.ai_service.get_provider", mock_get_provider)
        
        try:
            response = await client.post(
                "/api/v1/ai/chat/stream",
                json={"message": "Test message for persistence"},
                cookies=cookies,
            )
            assert response.status_code == 200
            
            content = response.text
            events = [line for line in content.split("\n") if line.startswith("data: ")]
            
            done_event = None
            for event in events:
                data = event[6:]
                if data == "[DONE]":
                    continue
                import json
                parsed = json.loads(data)
                if parsed.get("type") == "done":
                    done_event = parsed
            
            assert done_event is not None
            conversation_id = done_event.get("conversation_id")
            
            # Verify messages were saved in database
            from sqlalchemy import select
            from app.models.conversation import Message, ConversationRole
            from uuid import UUID
            
            result = await db_session.execute(
                select(Message).where(Message.conversation_id == UUID(conversation_id))
            )
            messages = result.scalars().all()
            
            # Should have user message and assistant message
            assert len(messages) == 2
            assert messages[0].role == ConversationRole.USER
            assert messages[0].content == "Test message for persistence"
            assert messages[1].role == ConversationRole.ASSISTANT
            assert messages[1].content == "This is the assistant response."
        finally:
            pass


class TestChatNonStreaming:
    """Tests for non-streaming chat endpoint (regression)."""

    @pytest.mark.asyncio
    async def test_chat_non_streaming_basic(self, client: AsyncClient, authenticated_user, monkeypatch):
        """Test basic non-streaming chat response."""
        user, cookies = authenticated_user
        
        def mock_get_provider(provider_name="mock"):
            return MockProvider(responses=[
                {"type": "content", "content": "Non-streaming response."},
            ])
        
        monkeypatch.setattr("app.services.ai_service.get_provider", mock_get_provider)
        
        try:
            response = await client.post(
                "/api/v1/ai/chat",
                json={"message": "Hello"},
                cookies=cookies,
            )
            assert response.status_code == 200
            data = response.json()
            assert "conversation_id" in data
            assert "message" in data
            assert data["message"]["role"] == "assistant"
            assert "Non-streaming response" in data["message"]["content"]
        finally:
            pass

    @pytest.mark.asyncio
    async def test_chat_non_streaming_with_tool_call(self, client: AsyncClient, authenticated_user, db_session, monkeypatch):
        """Test non-streaming chat with tool calling."""
        user, cookies = authenticated_user
        
        def mock_get_provider(provider_name="mock"):
            return MockProvider(responses=[
                {"type": "tool_call", "tool_call": {
                    "id": "call_123",
                    "type": "function",
                    "function": {"name": "create_task", "arguments": '{"title": "Test Task", "priority": "high"}'}
                }},
                {"type": "content", "content": "I've created the task for you."},
            ])
        
        monkeypatch.setattr("app.services.ai_service.get_provider", mock_get_provider)
        
        try:
            response = await client.post(
                "/api/v1/ai/chat",
                json={"message": "Create a task called Test Task"},
                cookies=cookies,
            )
            assert response.status_code == 200
            data = response.json()
            assert data["message"]["role"] == "assistant"
            assert "created" in data["message"]["content"].lower()
        finally:
            pass

    @pytest.mark.asyncio
    async def test_chat_non_streaming_persists_conversation(self, client: AsyncClient, authenticated_user, db_session, monkeypatch):
        """Test non-streaming chat persists conversation and messages."""
        user, cookies = authenticated_user
        
        def mock_get_provider(provider_name="mock"):
            return MockProvider(responses=[
                {"type": "content", "content": "Persisted response."},
            ])
        
        monkeypatch.setattr("app.services.ai_service.get_provider", mock_get_provider)
        
        try:
            response = await client.post(
                "/api/v1/ai/chat",
                json={"message": "Test persistence"},
                cookies=cookies,
            )
            assert response.status_code == 200
            data = response.json()
            conversation_id = data["conversation_id"]
            
            # Verify in database
            from sqlalchemy import select
            from app.models.conversation import Message, ConversationRole
            from uuid import UUID
            
            result = await db_session.execute(
                select(Message).where(Message.conversation_id == UUID(conversation_id))
            )
            messages = result.scalars().all()
            
            assert len(messages) == 2
            assert messages[0].role == ConversationRole.USER
            assert messages[1].role == ConversationRole.ASSISTANT
        finally:
            pass


class TestChatStreamEdgeCases:
    """Tests for edge cases in streaming chat."""

    @pytest.mark.asyncio
    async def test_chat_stream_long_message(self, client: AsyncClient, authenticated_user, monkeypatch):
        """Test streaming chat with long message."""
        user, cookies = authenticated_user
        
        def mock_get_provider(provider_name="mock"):
            return MockProvider(responses=[
                {"type": "content", "content": "Response to long message."},
            ])
        
        monkeypatch.setattr("app.services.ai_service.get_provider", mock_get_provider)
        
        try:
            long_message = "x" * 5000  # Within 8000 limit
            response = await client.post(
                "/api/v1/ai/chat/stream",
                json={"message": long_message},
                cookies=cookies,
            )
            assert response.status_code == 200
        finally:
            pass

    @pytest.mark.asyncio
    async def test_chat_stream_multiple_rounds(self, client: AsyncClient, authenticated_user, monkeypatch):
        """Test streaming chat with multiple tool calling rounds."""
        user, cookies = authenticated_user
        
        def mock_get_provider(provider_name="mock"):
            return MockProvider(responses=[
                {"type": "tool_call", "tool_call": {
                    "id": "call_1",
                    "type": "function",
                    "function": {"name": "create_task", "arguments": '{"title": "Task 1"}'}
                }},
                {"type": "tool_call", "tool_call": {
                    "id": "call_2",
                    "type": "function",
                    "function": {"name": "list_tasks", "arguments": '{}'}
                }},
                {"type": "content", "content": "Done with multiple rounds."},
            ])
        
        monkeypatch.setattr("app.services.ai_service.get_provider", mock_get_provider)
        
        try:
            response = await client.post(
                "/api/v1/ai/chat/stream",
                json={"message": "Create task and list tasks"},
                cookies=cookies,
            )
            assert response.status_code == 200
            
            content = response.text
            events = [line for line in content.split("\n") if line.startswith("data: ")]
            
            tool_call_count = 0
            for event in events:
                data = event[6:]
                if data == "[DONE]":
                    continue
                import json
                parsed = json.loads(data)
                if parsed.get("type") == "tool_call":
                    tool_call_count += 1
            
            assert tool_call_count == 2
        finally:
            pass