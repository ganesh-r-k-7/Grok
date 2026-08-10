from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.models.conversation import Conversation, Message, ConversationRole
from app.services.ai_service import AIService
from app.utils.errors import NotFoundError, ForbiddenError

router = APIRouter(tags=["AI"])


# Request/Response models
class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=8000)
    conversation_id: Optional[UUID] = None


class MessageResponse(BaseModel):
    id: UUID
    conversation_id: UUID
    role: ConversationRole
    content: str
    created_at: datetime

    class Config:
        from_attributes = True


class MessageListResponse(BaseModel):
    messages: list[MessageResponse]


@router.get("/conversations/{conversation_id}/messages", response_model=MessageListResponse)
async def get_conversation_messages(
    conversation_id: UUID,
    limit: int = Query(50, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get messages for a conversation."""
    ai_service = AIService(db)
    # Verify ownership
    await ai_service.get_conversation(conversation_id, user.id)
    messages = await ai_service.get_conversation_messages(conversation_id, user.id, limit=limit)
    return MessageListResponse(messages=[MessageResponse.model_validate(m) for m in messages])


class ChatResponse(BaseModel):
    conversation_id: UUID
    message: MessageResponse


class ConversationResponse(BaseModel):
    id: UUID
    user_id: UUID
    title: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ConversationListResponse(BaseModel):
    conversations: list[ConversationResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class ConversationCreate(BaseModel):
    title: str = Field(default="New Conversation", min_length=1, max_length=255)


class ConversationUpdate(BaseModel):
    title: str = Field(min_length=1, max_length=255)


@router.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Send a message to the AI and get a response."""
    ai_service = AIService(db)

    # Get or create conversation
    if request.conversation_id:
        conversation = await ai_service.get_conversation(request.conversation_id, user.id)
    else:
        # Create new conversation with first message as title basis
        conversation = await ai_service.create_conversation(user.id)

    # Process chat through AI service
    assistant_message = await ai_service.chat(
        conversation_id=conversation.id,
        user=user,
        message=request.message,
    )

    return ChatResponse(
        conversation_id=conversation.id,
        message=MessageResponse.model_validate(assistant_message),
    )


@router.get("/conversations", response_model=ConversationListResponse)
async def list_conversations(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all conversations for the authenticated user."""
    ai_service = AIService(db)
    conversations, total = await ai_service.list_conversations(user.id, page, page_size)

    total_pages = (total + page_size - 1) // page_size

    return ConversationListResponse(
        conversations=[ConversationResponse.model_validate(c) for c in conversations],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.post("/conversations", response_model=ConversationResponse, status_code=status.HTTP_201_CREATED)
async def create_conversation(
    request: ConversationCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new conversation."""
    ai_service = AIService(db)
    conversation = await ai_service.create_conversation(user.id, request.title)
    return ConversationResponse.model_validate(conversation)


@router.get("/conversations/{conversation_id}", response_model=ConversationResponse)
async def get_conversation(
    conversation_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a specific conversation by ID."""
    ai_service = AIService(db)
    conversation = await ai_service.get_conversation(conversation_id, user.id)
    return ConversationResponse.model_validate(conversation)


@router.patch("/conversations/{conversation_id}", response_model=ConversationResponse)
async def update_conversation(
    conversation_id: UUID,
    request: ConversationUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update a conversation (e.g., rename)."""
    ai_service = AIService(db)
    conversation = await ai_service.update_conversation_title(conversation_id, user.id, request.title)
    return ConversationResponse.model_validate(conversation)


@router.delete("/conversations/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_conversation(
    conversation_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a conversation."""
    ai_service = AIService(db)
    await ai_service.delete_conversation(conversation_id, user.id)