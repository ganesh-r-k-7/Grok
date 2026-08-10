"""AI Service for conversation management."""

from datetime import datetime, timezone
from typing import List, Optional, AsyncGenerator
from uuid import UUID
import json

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.conversation import Conversation, Message, ConversationRole
from app.models.user import User
from app.services.ai_providers.base import AIProvider, ChatMessage, ToolDefinition, ChatChunk
from app.services.ai_providers import get_provider
from app.services.task_tools import TaskTools
from app.utils.errors import NotFoundError, ForbiddenError
from app.config import get_settings

settings = get_settings()


SYSTEM_PROMPT = """You are GROK, a personal AI command center assistant.
You help users manage their tasks, schedule, and productivity.
You have access to tools for creating, listing, updating, and deleting tasks.
Use these tools when the user asks you to perform task-related actions.
Always confirm before deleting tasks.
Be concise and helpful."""


class AIService:
    """Service for managing AI conversations and messages."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self._provider: Optional[AIProvider] = None

    @property
    def provider(self) -> AIProvider:
        if self._provider is None:
            self._provider = get_provider()
        return self._provider

    async def create_conversation(self, user_id: UUID, title: str = "New Conversation") -> Conversation:
        """Create a new conversation for the user."""
        conversation = Conversation(
            user_id=user_id,
            title=title,
        )
        self.db.add(conversation)
        await self.db.commit()
        await self.db.refresh(conversation)
        return conversation

    async def get_conversation(self, conversation_id: UUID, user_id: UUID) -> Conversation:
        """Get a conversation by ID, verifying ownership."""
        result = await self.db.execute(
            select(Conversation)
            .options(selectinload(Conversation.messages))
            .where(Conversation.id == conversation_id, Conversation.user_id == user_id)
        )
        conversation = result.scalar_one_or_none()

        if not conversation:
            raise NotFoundError("Conversation", str(conversation_id))

        return conversation

    async def list_conversations(
        self,
        user_id: UUID,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Conversation], int]:
        """List conversations for a user with pagination."""
        base_query = select(Conversation).where(Conversation.user_id == user_id)

        # Count total
        count_query = select(func.count()).select_from(base_query.subquery())
        total_result = await self.db.execute(count_query)
        total = total_result.scalar_one()

        # Apply pagination and ordering
        query = base_query.order_by(Conversation.updated_at.desc()).offset((page - 1) * page_size).limit(page_size)
        result = await self.db.execute(query)
        conversations = result.scalars().all()

        return conversations, total

    async def update_conversation_title(
        self, conversation_id: UUID, user_id: UUID, title: str
    ) -> Conversation:
        """Update conversation title."""
        conversation = await self.get_conversation(conversation_id, user_id)
        conversation.title = title
        await self.db.commit()
        await self.db.refresh(conversation)
        return conversation

    async def delete_conversation(self, conversation_id: UUID, user_id: UUID) -> None:
        """Delete a conversation."""
        conversation = await self.get_conversation(conversation_id, user_id)
        await self.db.delete(conversation)
        await self.db.commit()

    async def add_message(
        self,
        conversation_id: UUID,
        role: ConversationRole,
        content: str,
        user_id: UUID,
    ) -> Message:
        """Add a message to a conversation, verifying ownership."""
        conversation = await self.get_conversation(conversation_id, user_id)

        message = Message(
            conversation_id=conversation_id,
            role=role,
            content=content,
        )
        self.db.add(message)
        await self.db.commit()
        await self.db.refresh(message)
        return message

    async def get_conversation_messages(
        self,
        conversation_id: UUID,
        user_id: UUID,
        limit: int = 50,
    ) -> list[Message]:
        """Get recent messages for a conversation, verifying ownership."""
        conversation = await self.get_conversation(conversation_id, user_id)

        result = await self.db.execute(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.desc())
            .limit(limit)
        )
        messages = result.scalars().all()
        return list(reversed(messages))

    async def build_context(
        self,
        conversation_id: UUID,
        user_id: UUID,
        max_messages: int = 20,
        system_prompt: str = "",
    ) -> list[ChatMessage]:
        """Build context for AI provider from conversation history."""
        messages = await self.get_conversation_messages(conversation_id, user_id, limit=max_messages)

        context = []
        if system_prompt:
            context.append(ChatMessage(role="system", content=system_prompt))

        for msg in messages:
            context.append(ChatMessage(role=msg.role.value, content=msg.content))

        return context

    async def _execute_tool_call(self, task_tools: TaskTools, tool_call: dict) -> dict:
        """Execute a single tool call and return the result."""
        tool_name = tool_call.get("function", {}).get("name")
        if not tool_name:
            return {"success": False, "error": "Missing tool name"}

        try:
            args = json.loads(tool_call.get("function", {}).get("arguments", "{}"))
        except json.JSONDecodeError:
            args = {}

        result = await task_tools.execute_tool(tool_name, args)
        return result

    async def chat(
        self,
        conversation_id: UUID,
        user: User,
        message: str,
    ) -> Message:
        """Process a chat message and get AI response (non-streaming)."""
        # Get the final response by consuming the streaming generator
        # Note: chat_stream adds the user message
        full_response = ""
        async for chunk in self.chat_stream(conversation_id, user, message):
            if chunk.type == "content" and chunk.content:
                full_response += chunk.content
            elif chunk.type == "error":
                # Return error message as response
                full_response = f"I encountered an error: {chunk.error}"
                break

        # If no response was generated, provide a default
        if not full_response:
            full_response = "I'm ready to help! What would you like to do?"

        # Add assistant message
        assistant_message = await self.add_message(
            conversation_id=conversation_id,
            role=ConversationRole.ASSISTANT,
            content=full_response,
            user_id=user.id,
        )

        return assistant_message

    async def chat_stream(
        self,
        conversation_id: UUID,
        user: User,
        message: str,
    ) -> AsyncGenerator[ChatChunk, None]:
        """Process a chat message and stream AI response with tool calling."""
        # Add user message
        await self.add_message(
            conversation_id=conversation_id,
            role=ConversationRole.USER,
            content=message,
            user_id=user.id,
        )

        # Build context with conversation history
        context = await self.build_context(
            conversation_id=conversation_id,
            user_id=user.id,
            max_messages=20,
            system_prompt=SYSTEM_PROMPT,
        )

        # Get task tools for AI
        task_tools = TaskTools(self.db, user)
        tools = task_tools.get_tool_definitions()

        # Tool calling loop - feed results back to model
        max_tool_rounds = 3
        tool_round = 0

        while tool_round < max_tool_rounds:
            tool_calls_in_round = []
            full_response = ""
            has_tool_calls = False

            async for chunk in self.provider.stream_chat(
                system_prompt=SYSTEM_PROMPT,
                messages=context,
                tools=[ToolDefinition(**t["function"]) for t in tools],
                tool_choice="auto",
                temperature=settings.AI_TEMPERATURE,
                max_tokens=settings.AI_MAX_TOKENS,
            ):
                if chunk.type == "content" and chunk.content:
                    full_response += chunk.content
                    yield chunk
                elif chunk.type == "tool_call":
                    has_tool_calls = True
                    tool_calls_in_round.append(chunk.tool_call)
                    yield chunk
                elif chunk.type == "error":
                    yield chunk
                    return
                elif chunk.type == "done":
                    yield chunk

            # If no tool calls, we're done
            if not has_tool_calls:
                if not full_response:
                    # Send a default response if nothing generated
                    yield ChatChunk(type="content", content="I'm ready to help! What would you like to do?")
                    yield ChatChunk(type="done")
                break

            # Execute all tool calls from this round
            for tool_call in tool_calls_in_round:
                result = await self._execute_tool_call(task_tools, tool_call)

                # Add tool result to context for next round
                tool_call_id = tool_call.get("id")
                context.append(ChatMessage(
                    role="tool",
                    content=json.dumps(result),
                    tool_call_id=tool_call_id,
                ))

                # Yield tool result for UI
                yield ChatChunk(type="tool_result", tool_result=result)

            tool_round += 1

        # Save the final assistant message
        # Note: The actual saving happens in the non-streaming chat() method
        # or can be done by the caller consuming this stream